set_option linter.unusedSimpArgs false

/-
Phase-9 (REAL BUG #16): GameData monster-stat accessor contract.

Pre-fix, `GameData.monster_attack/resistance/hp/critical_strike/initiative`
silently returned `{}` / `0` when the monster code was absent. The chain
`predict_win(s, gd, unknown)` then computed:
  player_hit > 0 ∧ rounds_to_kill = ceil(monster_hp=0 / player_hit) = 0
  monster_hit = 0 (no attack)
  ⇒ return True
i.e. the bot would judge ANY unknown monster as beatable. CLAUDE.md:
"Use only API data or fail with an error" — silent defaults masked the
upstream invariant (callers iterate `_monster_level` keys, so the monster
should always be known) into a false-positive verdict on the rare path
where the invariant breaks.

Post-fix, the accessors raise `KeyError` on absent keys; the single locus
is the accessor itself (no try/except needed in consumers — they already
iterate the known set).

This file models the contract over a finite `Map` (modelled as `List
(String × α)`). The Python `dict[k]` ⇒ KeyError correspondence is
modelled as `Option`-returning lookup, with two theorems pinning:
* `accessor_some_iff_present` — accessor returns `some v` iff the code
  is present in the map (post-fix contract).
* `silent_default_is_bug_witness` — the OLD silent-default pattern would
  swap `some` for the default, breaking the contract on an absent key.

Plus the `predictWinLite` witness: a minimal damage-model showing that
the pre-fix silent-zero defaults cause `predict_win`-style verdict to
return True on an unknown monster — the load-bearing bug counterexample.
-/

namespace Formal.GameDataAccessors

/-- A monster-stat lookup map: code → value. Python `dict`s are modelled
as `List (String × α)` with `lookup` = first-match semantics. -/
def Lookup (α : Type) := List (String × α)

/-- Post-fix accessor: `none` on absent (Python `KeyError`), `some v`
on present. Matches the Python `_monster_attack[code]` semantics
modelled at the contract level. -/
def accessor {α : Type} (m : Lookup α) (k : String) : Option α :=
  m.find? (fun p => p.1 = k) |>.map (·.2)

/-- Pre-fix (BUG) accessor: returns `default` instead of failing. Modeled
to anchor the bug counterexample. -/
def silentDefaultAccessor {α : Type} (m : Lookup α) (k : String)
    (default : α) : α :=
  match accessor m k with
  | none => default
  | some v => v

/-- `present m k` ↔ ∃ value, accessor returns it. The bookkeeping predicate
used to state the contract. -/
def present {α : Type} (m : Lookup α) (k : String) : Prop :=
  (m.find? (fun p => p.1 = k)).isSome

/-- Decidability for `present` (used by `decide`-witnesses). -/
instance {α : Type} (m : Lookup α) (k : String) : Decidable (present m k) := by
  unfold present
  exact inferInstance

/-! ### Post-fix accessor contract -/

/-- accessor-some-iff-present: the accessor returns `some _` exactly when
the key is in the map. -/
theorem accessor_some_iff_present {α : Type} (m : Lookup α) (k : String) :
    (accessor m k).isSome ↔ present m k := by
  unfold accessor present
  cases h : m.find? (fun p => p.1 = k) with
  | none => simp [h]
  | some v => simp [h]

/-- accessor-none-iff-absent: contrapositive. Absent ⇒ accessor yields `none`
(modelling the Python `KeyError` raise). -/
theorem accessor_none_iff_absent {α : Type} (m : Lookup α) (k : String) :
    accessor m k = none ↔ ¬ present m k := by
  unfold accessor present
  cases h : m.find? (fun p => p.1 = k) with
  | none => simp [h]
  | some v => simp [h]

/-- accessor-some-value: when present, the returned value is the snd of the
first matching pair. -/
theorem accessor_some_value {α : Type} (m : Lookup α) (k : String) (v : α)
    (h : m.find? (fun p => p.1 = k) = some (k, v)) :
    accessor m k = some v := by
  unfold accessor
  rw [h]; rfl

/-! ### Pre-fix bug-witness contract -/

/-- silent-default-on-absent: the BUGGY accessor returns `default` when the
key is absent — masking the real KeyError into a value. -/
theorem silentDefault_absent_returns_default {α : Type} (m : Lookup α)
    (k : String) (default : α) (h : ¬ present m k) :
    silentDefaultAccessor m k default = default := by
  unfold silentDefaultAccessor
  have hn : accessor m k = none := (accessor_none_iff_absent m k).mpr h
  rw [hn]

/-- silent-default-on-present: when the key IS present, the buggy accessor
still returns the real value (the bug only manifests on absent). -/
theorem silentDefault_present_returns_value {α : Type} (m : Lookup α)
    (k : String) (v default : α)
    (h : m.find? (fun p => p.1 = k) = some (k, v)) :
    silentDefaultAccessor m k default = v := by
  unfold silentDefaultAccessor
  rw [accessor_some_value m k v h]

/-! ### Bug counterexample: predictWinLite with silent zero defaults
returns True on an UNKNOWN monster.

`predictWinLite` is the minimal damage model:
  * playerHit = playerAtk
  * monsterHit = monsterAtk (silent 0 when monster unknown)
  * roundsToKill = ⌈monsterHp / playerHit⌉ (silent 0 when monster unknown)
  * roundsToDie = ⌈playerMaxHp / monsterHit⌉ (∞ when monsterHit = 0)
  * verdict: rTK ≤ rTD when player_first

Pre-fix: silent default ⇒ roundsToKill = 0, monsterHit = 0
         ⇒ ∞ ≥ 0 ⇒ True (unknown monster judged BEATABLE).
Post-fix: the accessor raises before reaching `predictWinLite` (modelled
as the precondition `present` here).
-/

/-- Minimal damage model: silent-default version, returns True on unknown. -/
def predictWinLite_buggy (atkMap hpMap : Lookup Nat) (k : String)
    (playerAtk : Nat) : Bool :=
  let monsterAtk := silentDefaultAccessor atkMap k 0
  let monsterHp := silentDefaultAccessor hpMap k 0
  -- roundsToKill = if playerAtk = 0 then ∞ else ceil(monsterHp / playerAtk)
  -- ceil(0/x) = 0, so unknown ⇒ roundsToKill = 0
  let rTK := if playerAtk = 0 then monsterHp + 1 else (monsterHp + playerAtk - 1) / playerAtk
  -- monsterHit = monsterAtk; if 0, monster can never kill, so rTD = ∞ sentinel
  -- We return True if monsterHit = 0 OR rTK ≤ rTD.
  if monsterAtk = 0 then true else rTK ≤ 1  -- crude; the True-on-unknown is the point

/-- Pre-fix bug witness: predictWinLite_buggy on an UNKNOWN monster
returns True, even with playerAtk = 1 and an empty atk/hp map. -/
theorem predictWinLite_buggy_unknown_returns_true :
    predictWinLite_buggy [] [] "unknown_monster" 1 = true := by
  decide

/-- Post-fix: the accessor returns `none` on the same input, so the verdict
is undefined (no silent True). -/
theorem accessor_unknown_returns_none :
    accessor ([] : Lookup Nat) "unknown_monster" = none := by
  decide

/-! ### Boundary witnesses -/

/-- Witness: a single-entry map. Present key returns the stored value. -/
theorem accessor_present_witness :
    accessor [("chicken", (10 : Nat))] "chicken" = some 10 := by decide

/-- Witness: a single-entry map. Absent key returns `none`. -/
theorem accessor_absent_witness :
    accessor [("chicken", (10 : Nat))] "dragon" = none := by decide

/-- Witness: silent-default version masks the same absence as `0`. -/
theorem silentDefault_absent_witness :
    silentDefaultAccessor [("chicken", (10 : Nat))] "dragon" 0 = 0 := by decide

/-- Witness: silent-default version returns the value on present. -/
theorem silentDefault_present_witness :
    silentDefaultAccessor [("chicken", (10 : Nat))] "chicken" 0 = 10 := by decide

/-! ### monster_level retained-silent-default contract -/

/-- `monster_level` keeps the silent zero default by documented design (it's
the "is this code a monster?" probe used by 5 consumers). We model that
explicitly as a separate accessor flavor so the Lean catalog distinguishes
the deliberate silent default from the bug-counterexample silent default. -/
def monsterLevelProbe (m : Lookup Nat) (k : String) : Nat :=
  silentDefaultAccessor m k 0

/-- monster-level probe: absent ⇒ 0 (documented). -/
theorem monsterLevelProbe_absent_returns_zero (m : Lookup Nat) (k : String)
    (h : ¬ present m k) : monsterLevelProbe m k = 0 := by
  unfold monsterLevelProbe
  exact silentDefault_absent_returns_default m k 0 h

/-- monster-level probe: present ⇒ stored level. -/
theorem monsterLevelProbe_present_returns_value (m : Lookup Nat) (k : String)
    (v : Nat) (h : m.find? (fun p => p.1 = k) = some (k, v)) :
    monsterLevelProbe m k = v := by
  unfold monsterLevelProbe
  exact silentDefault_present_returns_value m k v 0 h

end Formal.GameDataAccessors
