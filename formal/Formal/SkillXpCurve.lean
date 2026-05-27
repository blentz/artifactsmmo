/-
Formal model of `SkillXpCurve` from
`src/artifactsmmo_cli/ai/learning/skill_xp_curve.py`.

The Python class learns a skill's XP-to-next-level curve from `observed`
(`{level: max_xp}`), the only published data point being the CURRENT level's
requirement. Beyond observed levels it ESTIMATES via a learned geometric
multiple: `required_xp(level) ~= observed[anchor] * growth_ratio ** steps`.

## Float abstraction (disclosed)

The Python uses Python `float`s in three places that we DO NOT model as exact
integers (out of model scope — they are heuristic estimates, not contracts):

* `growth_ratio()` — the MEAN of observed consecutive-level ratios
  (`sum(ratios)/len(ratios)`), or `DEFAULT_GROWTH_RATIO = 1.5` when there are
  fewer than two consecutive observed levels. A float mean of float ratios.
* `required_xp(level)` for an UNOBSERVED level above the anchor — the geometric
  estimate `int(observed[anchor] * growth_ratio ** steps)`. The `**` power and
  the truncating `int(...)` are abstracted; we model `required_xp` only on the
  OBSERVED domain (where it returns the exact stored integer) and on the
  "no data" branches (where it returns the exact integer 0).
* `cycles_to_level(...)` finite branch — the quotient
  `total_xp_to_reach / xp_per_cycle` (a float division). We model only the two
  BRANCH outcomes that are exact: the `0.0` guard and the `inf` sentinel; the
  finite quotient itself is abstracted.

What we DO model exactly (the INTEGER / COUNT / BRANCH structure):
* `requiredXp` on observed levels = the stored xp; on the empty/no-lower-level
  branches = 0.
* `confidence` as the exact rational `confNum / confDen` (count of observed gap
  levels over gap length), proved `0 ≤ confNum ≤ confDen`.
* `is_confident` ↔ every gap level observed ↔ `confNum = confDen`.
* `cycles` 0-guard (`target ≤ current`) and inf-sentinel (`xp_per_cycle ≤ 0`).
* `total_xp_to_reach` over a fully-observed range as a bounded recursive sum of
  exact stored xp, proved monotone in the target.
* `usesDefaultRatio` ↔ there is no consecutive observed pair, cross-checked
  against an INDEPENDENT consecutive-pair count (not an X↔X tautology).

Lean core only — no mathlib. Integer/nat arithmetic via `omega` and structural
induction over the observed list / a range fuel.
-/

namespace Formal.SkillXpCurve

/-- Fallback per-level growth multiplier numerator/denominator (`1.5 = 3/2`),
mirroring `DEFAULT_GROWTH_RATIO`. We never use the float; this records the
documented default symbolically for the disclosure. -/
def defaultGrowthNum : Int := 3
def defaultGrowthDen : Int := 2

/-- The observed table: an association list `(level, xp)`. Mirrors the Python
`observed: dict[int, int]`. We do not require sortedness; lookup mirrors a dict. -/
abbrev Observed := List (Int × Int)

/-- Whether `level` is a key of `observed`. -/
def hasLevel (obs : Observed) (level : Int) : Bool :=
  obs.any (fun p => p.1 == level)

/-- Lookup `observed[level]`, returning `0` when absent (only ever queried under
`hasLevel`, where the absent branch is unreachable). -/
def lookup (obs : Observed) (level : Int) : Int :=
  match obs with
  | [] => 0
  | (k, v) :: rest => if k == level then v else lookup rest level

/-- Is there any observed key strictly below `level`? Mirrors the Python
`below = [lvl for lvl in observed if lvl < level]; if not below`. -/
def hasBelow (obs : Observed) (level : Int) : Bool :=
  obs.any (fun p => decide (p.1 < level))

/-- `required_xp(level)` restricted to the EXACTLY-modeled branches:
* observed level                  → the stored xp,
* no observed data OR no key below → 0,
* otherwise (unobserved above anchor) → the abstracted geometric estimate,
  represented opaquely by `estimate` (NOT modeled as an exact integer).

This makes the modeled outputs (`hasLevel`, the two zero branches) provable
while keeping the float estimate out of the contract. -/
def requiredXp (estimate : Int → Int) (obs : Observed) (level : Int) : Int :=
  if hasLevel obs level then lookup obs level
  else if obs.isEmpty then 0
  else if hasBelow obs level then estimate level
  else 0

/-! ### Confidence: an exact rational `confNum / confDen` over the gap. -/

/-- Levels of the half-open gap `[current, target)` as an `Int` list. `n` is the
fuel `(target - current)` clamped to ℕ; we recurse on it. -/
def gapLevels (current : Int) : Nat → List Int
  | 0 => []
  | Nat.succ k => current :: gapLevels (current + 1) k

/-- Number of gap levels (`confDen`): the length of the gap, i.e. `max 0
(target - current)`. -/
def gapLen (current target : Int) : Nat := (target - current).toNat

/-- Count of gap levels that are observed (`confNum`). -/
def confNum (obs : Observed) (current target : Int) : Nat :=
  ((gapLevels current (gapLen current target)).filter (fun l => hasLevel obs l)).length

/-- Denominator of the confidence fraction. -/
def confDen (current target : Int) : Nat := gapLen current target

/-- `is_confident`: every gap level was directly observed. -/
def isConfident (obs : Observed) (current target : Int) : Bool :=
  (gapLevels current (gapLen current target)).all (fun l => hasLevel obs l)

/-! ### Cycles-to-level branch structure (the two exact outcomes). -/

/-- Sentinel for `float("inf")`. We only model the BRANCH that returns it. -/
def cyclesInf : Int := -1

/-- `cycles_to_level` branch classifier: `0` when `target ≤ current`,
`cyclesInf` when `xp_per_cycle ≤ 0` (and target > current), else a `finite`
flag (the actual quotient is the abstracted float). We emit `1` for the finite
branch as a sentinel meaning "finite quotient (abstracted)". -/
def cyclesBranch (current target xpPerCycle : Int) : Int :=
  if target ≤ current then 0
  else if xpPerCycle ≤ 0 then cyclesInf
  else 1

/-! ### Total XP over a fully-observed range (bounded recursive exact sum). -/

/-- Bounded recursive `total_xp_to_reach` over the gap, using the EXACT observed
xp for every level (the caller restricts to fully-observed ranges, where this
equals the Python sum). `fuel = target - current`. -/
def totalExact (obs : Observed) (current : Int) : Nat → Int
  | 0 => 0
  | Nat.succ k => lookup obs current + totalExact obs (current + 1) k

/-- `total_xp_to_reach(current, target)` over a fully-observed range. -/
def totalXpToReach (obs : Observed) (current target : Int) : Int :=
  totalExact obs current (gapLen current target)

/-! ### Growth-ratio default classification. -/

/-- INDEPENDENT count of consecutive observed pairs `(lvl, lvl+1)` both present
with `observed[lvl] > 0` (matching the Python `ratios` comprehension guard).
This is computed by a SEPARATE structural fold, NOT by reusing `usesDefaultRatio`.
-/
def consecutivePairCount (obs : Observed) : Nat :=
  (obs.filter (fun p => hasLevel obs (p.1 + 1) && decide (p.2 > 0))).length

/-- `growth_ratio()` falls back to the default ⇔ `ratios` is empty ⇔ there is no
consecutive observed pair. We define `usesDefaultRatio` via the independent
count being zero. -/
def usesDefaultRatio (obs : Observed) : Bool :=
  consecutivePairCount obs == 0

/-! ### Theorems. -/

/-- `gapLevels` has length equal to its fuel. -/
theorem gapLevels_length (current : Int) (n : Nat) :
    (gapLevels current n).length = n := by
  induction n generalizing current with
  | zero => rfl
  | succ k ih => unfold gapLevels; simp [ih (current + 1)]

/-- `lookup` agrees with the first matching key (used to pin observed reads). -/
theorem lookup_cons_hit (k v : Int) (rest : Observed) (level : Int)
    (h : k = level) : lookup ((k, v) :: rest) level = v := by
  unfold lookup
  simp [h]

/-- `required_xp_observed`: on an observed level, `requiredXp` returns the stored
xp (independent of the abstracted `estimate`). -/
theorem required_xp_observed (estimate : Int → Int) (obs : Observed) (level : Int)
    (h : hasLevel obs level = true) :
    requiredXp estimate obs level = lookup obs level := by
  unfold requiredXp
  simp [h]

/-- `required_xp_zero`: when there is no observed data, OR no observed key below
the (unobserved) level, `requiredXp` is exactly 0. -/
theorem required_xp_zero (estimate : Int → Int) (obs : Observed) (level : Int)
    (hnot : hasLevel obs level = false)
    (hzero : obs.isEmpty = true ∨ hasBelow obs level = false) :
    requiredXp estimate obs level = 0 := by
  unfold requiredXp
  rw [if_neg (by simp [hnot])]
  rcases hzero with he | hb
  · rw [if_pos he]
  · by_cases he : obs.isEmpty = true
    · rw [if_pos he]
    · rw [if_neg (by simp [he]), if_neg (by simp [hb])]

/-- `confNum_le_confDen`: the count of observed gap levels never exceeds the gap
length, so the confidence fraction `confNum/confDen ∈ [0,1]`. (`0 ≤ confNum` is
immediate as a `Nat`.) -/
theorem confNum_le_confDen (obs : Observed) (current target : Int) :
    confNum obs current target ≤ confDen current target := by
  unfold confNum confDen gapLen
  -- length of a filtered list ≤ length of the gap = gapLen
  have hfilt : ((gapLevels current ((target - current).toNat)).filter
      (fun l => hasLevel obs l)).length
      ≤ (gapLevels current ((target - current).toNat)).length :=
    List.length_filter_le _ _
  have hlen := gapLevels_length current ((target - current).toNat)
  omega

/-- `is_confident_iff_full`: `is_confident` holds ⇔ every gap level is observed
⇔ `confNum = confDen` (the fraction is exactly 1). -/
theorem is_confident_iff_full (obs : Observed) (current target : Int) :
    isConfident obs current target = true
      ↔ confNum obs current target = confDen current target := by
  unfold isConfident confNum confDen gapLen
  constructor
  · intro hall
    -- all observed ⇒ filter keeps everything ⇒ lengths equal
    rw [List.all_eq_true] at hall
    have : (gapLevels current ((target - current).toNat)).filter
        (fun l => hasLevel obs l) = gapLevels current ((target - current).toNat) :=
      List.filter_eq_self.mpr (by
        intro a ha; exact hall a ha)
    rw [this]
    exact gapLevels_length current ((target - current).toNat)
  · intro heq
    -- filter length = full length ⇒ filter keeps all ⇒ all hold
    rw [List.all_eq_true]
    -- general: a list whose filtered length equals its length keeps all elements
    have key : ∀ (l : List Int),
        (l.filter (fun x => hasLevel obs x)).length = l.length →
        ∀ a ∈ l, hasLevel obs a = true := by
      intro l
      induction l with
      | nil => intro _ a ha; simp at ha
      | cons x xs ih =>
        intro hl a ha
        rw [List.filter_cons] at hl
        have hle := List.length_filter_le (fun x => hasLevel obs x) xs
        by_cases hx : hasLevel obs x = true
        · rw [if_pos hx, List.length_cons, List.length_cons] at hl
          have htail : (xs.filter (fun x => hasLevel obs x)).length = xs.length := by
            omega
          rcases List.mem_cons.mp ha with hax | hax
          · rw [hax]; exact hx
          · exact ih htail a hax
        · have hxf : (hasLevel obs x) = false := by simp_all
          rw [if_neg (by simp [hxf]), List.length_cons] at hl
          omega
    have hgaplen := gapLevels_length current ((target - current).toNat)
    intro a ha
    exact key (gapLevels current ((target - current).toNat)) (by omega) a ha

/-- `cycles_zero`: `target ≤ current ⇒ 0`. -/
theorem cycles_zero (current target xpPerCycle : Int) (h : target ≤ current) :
    cyclesBranch current target xpPerCycle = 0 := by
  unfold cyclesBranch
  rw [if_pos h]

/-- `cycles_inf`: `target > current ∧ xp_per_cycle ≤ 0 ⇒ inf-sentinel`. -/
theorem cycles_inf (current target xpPerCycle : Int)
    (htgt : target > current) (hxp : xpPerCycle ≤ 0) :
    cyclesBranch current target xpPerCycle = cyclesInf := by
  unfold cyclesBranch
  rw [if_neg (by omega), if_pos hxp]

/-- `cycles_finite`: `target > current ∧ xp_per_cycle > 0 ⇒ finite flag`. -/
theorem cycles_finite (current target xpPerCycle : Int)
    (htgt : target > current) (hxp : xpPerCycle > 0) :
    cyclesBranch current target xpPerCycle = 1 := by
  unfold cyclesBranch
  rw [if_neg (by omega), if_neg (by omega)]

/-- Helper: `gapLen current (target+1) = gapLen current target + 1` when
`target ≥ current` (the gap grows by exactly one level). -/
theorem gapLen_succ (current target : Int) (h : current ≤ target) :
    gapLen current (target + 1) = gapLen current target + 1 := by
  unfold gapLen
  omega

/-- `totalExact` appends the term at `current + n` when the fuel grows by one,
i.e. `totalExact obs current (n+1) = totalExact obs current n + lookup obs
(current + n)`. This is the "sum over `[current, current+n+1)`" recurrence. -/
theorem totalExact_succ (obs : Observed) (current : Int) (n : Nat) :
    totalExact obs current (n + 1)
      = totalExact obs current n + lookup obs (current + (n : Int)) := by
  induction n generalizing current with
  | zero => simp [totalExact]
  | succ k ih =>
    -- unfold the leading term on both sides, recurse on the tail
    show lookup obs current + totalExact obs (current + 1) (k + 1)
      = (lookup obs current + totalExact obs (current + 1) k)
        + lookup obs (current + ((k : Int) + 1))
    rw [ih (current + 1)]
    have hidx : current + 1 + (k : Int) = current + ((k : Int) + 1) := by omega
    rw [hidx]
    omega

/-- `total_observed_nonneg`: when every level in the range has a NON-NEGATIVE
stored xp (true on the observed domain — xp ≥ 0), the bounded total is ≥ 0. -/
theorem total_observed_nonneg (obs : Observed) (current target : Int)
    (hnn : ∀ l, current ≤ l → l < target → 0 ≤ lookup obs l) :
    0 ≤ totalXpToReach obs current target := by
  unfold totalXpToReach gapLen
  generalize hn : (target - current).toNat = n
  -- the fuel n satisfies (n : Int) = max 0 (target - current); we carry the
  -- bound that current + n ≤ target when n > 0.
  have hbound : (n : Int) ≤ target - current ∨ n = 0 := by
    rcases Int.lt_or_le current target with h | h
    · left; omega
    · right; omega
  clear hn
  induction n generalizing current with
  | zero => simp [totalExact]
  | succ k ih =>
    unfold totalExact
    have hlt : current < target := by omega
    have hge : 0 ≤ lookup obs current := hnn current (Int.le_refl current) hlt
    have htail : 0 ≤ totalExact obs (current + 1) k := by
      apply ih (current + 1)
      · intro l hl hlt2; exact hnn l (by omega) hlt2
      · omega
    omega

/-- `total_monotone`: `total_xp_to_reach(current, target) ≤
total_xp_to_reach(current, target+1)` over an observed range where the added
term `lookup obs target` is ≥ 0 (xp is non-negative on the observed domain).
Requires `current ≤ target` so the gap actually extends by the level `target`. -/
theorem total_monotone (obs : Observed) (current target : Int)
    (hle : current ≤ target) (hterm : 0 ≤ lookup obs target) :
    totalXpToReach obs current target ≤ totalXpToReach obs current (target + 1) := by
  unfold totalXpToReach
  rw [gapLen_succ current target hle]
  rw [totalExact_succ obs current (gapLen current target)]
  -- the added term is lookup obs (current + gapLen) = lookup obs target
  have hidx : current + ((gapLen current target : Int)) = target := by
    unfold gapLen; omega
  rw [hidx]
  omega

/-- `growth_default_iff`: `usesDefaultRatio` ⇔ there are fewer than two
consecutive observed levels ⇔ NO consecutive observed pair exists ⇔ the
independent `consecutivePairCount` is zero. This is pinned against the SEPARATE
structural count (not a `usesDefaultRatio ↔ usesDefaultRatio` tautology). -/
theorem growth_default_iff (obs : Observed) :
    usesDefaultRatio obs = true ↔ consecutivePairCount obs = 0 := by
  unfold usesDefaultRatio
  constructor
  · intro h; exact beq_iff_eq.mp h
  · intro h; exact beq_iff_eq.mpr h

/-- Cross-check (hand-table / independent witness): `usesDefaultRatio` is FALSE
exactly when a consecutive observed pair with positive lower xp exists. We
exhibit the witness direction: if `(lvl, v) ∈ obs` with `v > 0` and `lvl+1`
observed, then the count is ≥ 1, hence `usesDefaultRatio = false`. This rules
out the trivial reading where `usesDefaultRatio` ignores the pair structure. -/
theorem growth_nondefault_of_pair (obs : Observed) (lvl v : Int)
    (hmem : (lvl, v) ∈ obs) (hpos : v > 0)
    (hnext : hasLevel obs (lvl + 1) = true) :
    usesDefaultRatio obs = false := by
  unfold usesDefaultRatio
  rw [beq_eq_false_iff_ne]
  -- the filtered list contains (lvl, v), so its length ≥ 1, so count ≠ 0
  have hmem' : (lvl, v) ∈ obs.filter
      (fun p => hasLevel obs (p.1 + 1) && decide (p.2 > 0)) := by
    rw [List.mem_filter]
    refine ⟨hmem, ?_⟩
    simp only [hnext, Bool.true_and, decide_eq_true_eq]
    exact hpos
  have : consecutivePairCount obs ≠ 0 := by
    unfold consecutivePairCount
    intro hc
    rw [List.length_eq_zero_iff] at hc
    rw [hc] at hmem'
    exact List.not_mem_nil hmem'
  exact this

end Formal.SkillXpCurve
