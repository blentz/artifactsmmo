-- @concept: core, planner @property: safety, totality
/-
Formal model of `next_craft_target_pure`
(`src/artifactsmmo_cli/ai/next_craft_core.py`): the deterministic next-action
generator that replaces a 52K-node GOAP A* re-run for craft-chain goals.

It walks THE ONE OBTAIN MODEL (`ai/obtain_sources.Source`): at each item the
priority-ordered `sources` list is consulted FIRST (WITHDRAW, RECYCLE preempt
even a craft; a CRAFT source defers to the recipe descent; GATHER/BUY/DROP are
taken immediately), and only when no source applies does the recipe descent run
(gather a recipe-less leaf, withdraw a banked short input, else craft).

CODE FACTS mirrored (next_craft_core.py):
  nextCraftTarget  = None when qty ≤ owned target  (already satisfied)
               | Some (nextHelper ...) otherwise

  nextHelper (fuel+1)  →
     let deficit = need - owned item
     match firstStep (sources item) with          -- the source loop
     | some na → na                                -- first applicable source wins
     | none →
       match recipes item with
       | none       → gather (raw resource)
       | some inputs →
         match inputs.find? (fun p => owned p.1 < p.2 * deficit) with
         | some p → withdraw p (banked) else recurse into p.1
         | none   → craft (all inputs satisfied)

  _step_for (stepFor): every non-CRAFT source is capped at
  `min(deficit, capacity)`; RECYCLE is ADDITIONALLY bounded by the LIVE owned
  stock of the source item (`owned src.code * yieldPer`) so a second visit to the
  same item recognises the recycle source is now exhausted (the partial-recovery
  mixed plan). A zero cap ⇒ `none` (the source gives nothing right now → fall
  through to the next-priority source or the recipe descent).

ROLES proved:
  * validity  — nextCraftTarget = none ↔ qty ≤ owned target
  * ordering  — craft returned ⇒ inputs.find? (short predicate) = none
                (never craft before inputs ready); a source never emits craft
  * shortness — nextHelper always returns qty ≥ 1 when initial deficit is positive
  * withdraw  — a withdraw is genuinely served (banked) and never over-asks
                (descent withdraws are bank-guarded; withdraw SOURCES under the
                obtain-model well-formedness `WFWithdraw`, which `obtain_sources`
                satisfies — capacity is the bank stock).

Lean core only — no mathlib.
-/

namespace Formal.NextCraftAction

/-- The six ways an item can be obtained (mirrors `obtain_sources.SourceKind`):
gather a raw resource, craft from inputs, withdraw a banked copy, recycle a
licensed surplus item, buy from an NPC, or take a monster drop. -/
inductive Kind where
  | gather
  | craft
  | withdraw
  | recycle
  | buy
  | drop
  deriving DecidableEq, Repr, Inhabited

/-- The next single action toward a target: what item, how to produce it, how
many needed, and the SOURCE's own code (RECYCLE's destroyed item, BUY's npc,
DROP's monster); `""` when the source's own code is `item` itself (CRAFT,
WITHDRAW, plain GATHER). Mirrors the 4-field Python `NextAction`. -/
structure NextAction where
  item : String
  kind : Kind
  qty  : Nat
  code : String
  deriving DecidableEq, Repr, Inhabited

/-- One concrete obtain source (mirrors `obtain_sources.Source`).

`code` is the source's own code (the resource for GATHER, the item itself for
CRAFT/WITHDRAW, the item-to-DESTROY for RECYCLE, the npc for BUY, the monster
for DROP). `yieldPer` is the units of the TARGET per single application.
`capacity` is the max units the source can deliver right now. -/
structure Source where
  kind : Kind
  code : String
  yieldPer : Nat
  capacity : Nat
  deriving DecidableEq, Repr, Inhabited

/-- Ceil division `⌈a / b⌉` on `Nat` (mirrors Python `math.ceil(a / b)` for
`b ≥ 1`). -/
def ceilDiv (a b : Nat) : Nat := (a + b - 1) / b

/-! ## Core definitions (mirror Python `_step_for` / `_next`) -/

/-- The units a source delivers right now: capped at `min(deficit, capacity)`;
RECYCLE additionally bounded by the LIVE owned stock of the source item. -/
def sourceQty (src : Source) (deficit : Nat) (owned : String → Nat) : Nat :=
  match src.kind with
  | Kind.recycle => min deficit (min src.capacity (owned src.code * src.yieldPer))
  | _            => min deficit src.capacity

/-- Translate one non-CRAFT source into the immediate step for `item`, or `none`
if the source is exhausted right now (mirrors `next_craft_core._step_for`). The
`code` is `""` when the source's own code equals `item`; a zero cap yields
`none`. -/
def stepFor (src : Source) (item : String) (deficit : Nat)
    (owned : String → Nat) : Option NextAction :=
  if sourceQty src deficit owned = 0 then none
  else some ⟨item, src.kind, sourceQty src deficit owned,
             if src.code = item then "" else src.code⟩

/-- Scan the priority-ordered sources for `item`, returning the first applicable
non-CRAFT step; stop (→ `none`, deferring to the recipe descent) at the first
CRAFT source. Mirrors the `for src in sources.get(item, ())` loop with its
`break`-on-CRAFT. -/
def firstStep (item : String) (deficit : Nat) (owned : String → Nat)
    : List Source → Option NextAction
  | []          => none
  | src :: rest =>
      if src.kind = Kind.craft then none
      else match stepFor src item deficit owned with
        | some na => some na
        | none    => firstStep item deficit owned rest

/-- Walk the obtain model / recipe DAG to find the deepest actionable step.

`fuel` bounds recursion for totality; acyclic recipe data guarantees it is
never exhausted (Python uses `len(recipes)+1` at the top level).

The priority-ordered `sources item` is consulted first (`firstStep`); on `none`
the recipe descent runs exactly as the pre-existing recipe-tree walk did. -/
def nextHelper
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned   : String → Nat)
    (bank    : String → Nat)
    : String → Nat → Nat → NextAction
  | item, need, 0 =>
      -- fuel exhausted (totality guard): Python still consults sources here,
      -- then falls to a gather (recipe descent cannot recurse further).
      (firstStep item (need - owned item) owned (sources item)).getD
        ⟨item, .gather, need - owned item, ""⟩
  | item, need, fuel + 1 =>
      match firstStep item (need - owned item) owned (sources item) with
      | some na => na
      | none =>
        match recipes item with
        | none        => ⟨item, .gather, need - owned item, ""⟩   -- raw resource: gather
        | some inputs =>
            match inputs.find? (fun p => owned p.1 < p.2 * (need - owned item)) with
            | some p  =>
                let req := p.2 * (need - owned item)
                if bank p.1 = 0 then
                  nextHelper recipes sources owned bank p.1 req fuel     -- not banked: recurse
                else
                  ⟨p.1, .withdraw, min (bank p.1) (req - owned p.1), ""⟩ -- banked input: withdraw
            | none    => ⟨item, .craft, need - owned item, ""⟩      -- all inputs on hand: craft

/-- Entry point: returns `none` when the target is already satisfied, else `some`
next action. Mirrors `next_craft_target_pure`; caller passes `fuel = |recipes| + 1`. -/
def nextCraftTarget
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned   : String → Nat)
    (bank    : String → Nat)
    (target  : String)
    (qty fuel : Nat) : Option NextAction :=
  if qty ≤ owned target then none
  else some (nextHelper recipes sources owned bank target qty fuel)

/-! ## stepFor / firstStep spec lemmas -/

/-- **STEPFOR-SPEC.** A `stepFor` result mirrors its source: same item, same
kind, positive qty, and (for non-recycle kinds) qty ≤ capacity. -/
theorem stepFor_some {src : Source} {item : String} {deficit : Nat}
    {owned : String → Nat} {na : NextAction}
    (h : stepFor src item deficit owned = some na) :
    na.item = item ∧ na.kind = src.kind ∧ 1 ≤ na.qty ∧
      (src.kind ≠ Kind.recycle → na.qty ≤ src.capacity) := by
  simp only [stepFor] at h
  split at h
  · simp at h
  · rename_i hne
    simp only [Option.some.injEq] at h
    subst h
    refine ⟨rfl, rfl, Nat.one_le_iff_ne_zero.mpr hne, ?_⟩
    intro hrec
    simp only [sourceQty]
    cases hk : src.kind <;>
      first
        | (exact absurd hk hrec)
        | exact Nat.min_le_right _ _

/-- **FIRSTSTEP-SPEC.** When the source loop returns `some na`, that step is the
`stepFor` image of some non-CRAFT source in the list. -/
theorem firstStep_spec (item : String) (deficit : Nat) (owned : String → Nat) :
    ∀ (srcs : List Source) (na : NextAction),
      firstStep item deficit owned srcs = some na →
      ∃ s, s ∈ srcs ∧ s.kind ≠ Kind.craft ∧ stepFor s item deficit owned = some na := by
  intro srcs
  induction srcs with
  | nil => intro na h; simp [firstStep] at h
  | cons src rest ih =>
    intro na h
    simp only [firstStep] at h
    by_cases hc : src.kind = Kind.craft
    · rw [if_pos hc] at h; simp at h
    · rw [if_neg hc] at h
      cases hstep : stepFor src item deficit owned with
      | none =>
        simp only [hstep] at h
        obtain ⟨s, hmem, hnc, hs⟩ := ih na h
        exact ⟨s, List.mem_cons_of_mem _ hmem, hnc, hs⟩
      | some na0 =>
        simp only [hstep, Option.some.injEq] at h
        exact ⟨src, List.mem_cons_self, hc, by rw [hstep, h]⟩

/-! ## Theorem 1: validity -/

/-- **VALIDITY.** `nextCraftTarget` returns `none` iff the target quantity is
already satisfied (`qty ≤ owned target`). -/
theorem nextCraftTarget_none_iff
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned   : String → Nat)
    (bank    : String → Nat)
    (target  : String)
    (qty fuel : Nat) :
    nextCraftTarget recipes sources owned bank target qty fuel = none ↔ qty ≤ owned target := by
  simp [nextCraftTarget]

/-! ## Theorem 2: ordering (safety) -/

/-- **ORDERING.** If `nextHelper` returns a `craft` action, then the recipe
inputs for that item are all on hand (`inputs.find?` with the "short" predicate
= `none`). A craft is emitted only from the recipe descent — a source never
emits craft (the loop breaks on a CRAFT source). -/
theorem nextHelper_craft_inputs_satisfied
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned   : String → Nat)
    (bank    : String → Nat) :
    ∀ (item : String) (need fuel : Nat) (result : NextAction),
      nextHelper recipes sources owned bank item need fuel = result →
      result.kind = Kind.craft →
      ∃ inputs,
        recipes result.item = some inputs ∧
        inputs.find? (fun p => decide (owned p.1 < p.2 * result.qty)) = none := by
  intro item need fuel
  induction fuel generalizing item need with
  | zero =>
    intro result h hkind
    simp only [nextHelper] at h
    cases hfs : firstStep item (need - owned item) owned (sources item) with
    | none => simp only [hfs, Option.getD_none] at h; subst h; simp at hkind
    | some na =>
      simp only [hfs, Option.getD_some] at h; subst h
      obtain ⟨s, _, hnc, hstep⟩ := firstStep_spec item (need - owned item) owned _ _ hfs
      rw [(stepFor_some hstep).2.1] at hkind; exact absurd hkind hnc
  | succ n ih =>
    intro result h hkind
    simp only [nextHelper] at h
    cases hfs : firstStep item (need - owned item) owned (sources item) with
    | some na =>
      simp only [hfs] at h; subst h
      obtain ⟨s, _, hnc, hstep⟩ := firstStep_spec item (need - owned item) owned _ _ hfs
      rw [(stepFor_some hstep).2.1] at hkind; exact absurd hkind hnc
    | none =>
      simp only [hfs] at h
      split at h
      · subst h; simp at hkind
      · rename_i inputs heq
        split at h
        · rename_i p _
          split at h
          · exact ih p.1 (p.2 * (need - owned item)) result h hkind
          · subst h; simp at hkind
        · rename_i hnone
          subst h
          exact ⟨inputs, heq, hnone⟩

/-! ## Theorem 3: shortness -/

/-- **SHORTNESS LEMMA.** `nextHelper` returns `qty ≥ 1` when the initial deficit
is positive. -/
theorem nextHelper_qty_pos
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned   : String → Nat)
    (bank    : String → Nat) :
    ∀ (item : String) (need fuel : Nat),
      owned item < need →
      1 ≤ (nextHelper recipes sources owned bank item need fuel).qty := by
  intro item need fuel
  induction fuel generalizing item need with
  | zero =>
    intro hdef
    simp only [nextHelper]
    cases hfs : firstStep item (need - owned item) owned (sources item) with
    | none => simp only [Option.getD_none]; omega
    | some na =>
      simp only [Option.getD_some]
      obtain ⟨s, _, _, hstep⟩ := firstStep_spec item (need - owned item) owned _ _ hfs
      exact (stepFor_some hstep).2.2.1
  | succ n ih =>
    intro hdef
    simp only [nextHelper]
    cases hfs : firstStep item (need - owned item) owned (sources item) with
    | some na =>
      dsimp only
      obtain ⟨s, _, _, hstep⟩ := firstStep_spec item (need - owned item) owned _ _ hfs
      exact (stepFor_some hstep).2.2.1
    | none =>
      dsimp only
      split
      · simp; omega
      · split
        · rename_i p hp
          have hlt : owned p.1 < p.2 * (need - owned item) := by
            have := List.find?_some hp
            simp only [decide_eq_true_eq] at this
            exact this
          split
          · apply ih; omega
          · rename_i hbank
            have hb : 1 ≤ bank p.1 := Nat.one_le_iff_ne_zero.mpr hbank
            simp only [Nat.le_min]
            omega
        · simp; omega

/-- **SHORTNESS.** When `nextCraftTarget` returns `some action`, the action's qty
is ≥ 1 (a genuine positive deficit). -/
theorem nextCraftTarget_qty_pos
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned   : String → Nat)
    (bank    : String → Nat)
    (target  : String)
    (qty fuel : Nat)
    (result  : NextAction)
    (h       : nextCraftTarget recipes sources owned bank target qty fuel = some result) :
    1 ≤ result.qty := by
  simp only [nextCraftTarget] at h
  split at h
  · simp at h
  · rename_i hlt
    simp only [Option.some.injEq] at h
    subst h
    apply nextHelper_qty_pos
    omega

/-! ## Theorem 4: withdraw validity (under obtain-model well-formedness) -/

/-- **WELL-FORMED WITHDRAW SOURCES.** Every WITHDRAW source for item `i` can
deliver no more than the bank holds of `i` — exactly how `obtain_sources`
constructs them (`capacity = bank stock`, `yieldPer = 1`). Non-vacuous: the
empty source map and every real `obtain_sources` output satisfy it. -/
def WFWithdraw (sources : String → List Source) (bank : String → Nat) : Prop :=
  ∀ (i : String) (s : Source), s ∈ sources i → s.kind = Kind.withdraw → s.capacity ≤ bank i

/-- **WITHDRAW-BANKED.** If `nextHelper` returns a `withdraw`, the withdrawn item
is genuinely banked. Descent withdraws are bank-guarded outright; withdraw
SOURCES rely on `WFWithdraw` (capacity ≤ bank), so a positive-qty withdraw
source forces a positive bank. -/
theorem nextHelper_withdraw_banked
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned   : String → Nat)
    (bank    : String → Nat)
    (hwf     : WFWithdraw sources bank) :
    ∀ (item : String) (need fuel : Nat) (result : NextAction),
      nextHelper recipes sources owned bank item need fuel = result →
      result.kind = Kind.withdraw →
      0 < bank result.item := by
  intro item need fuel
  induction fuel generalizing item need with
  | zero =>
    intro result h hkind
    simp only [nextHelper] at h
    cases hfs : firstStep item (need - owned item) owned (sources item) with
    | none => simp only [hfs, Option.getD_none] at h; subst h; simp at hkind
    | some na =>
      simp only [hfs, Option.getD_some] at h; subst h
      obtain ⟨s, hmem, _, hstep⟩ := firstStep_spec item (need - owned item) owned _ _ hfs
      have hspec := stepFor_some hstep
      have hkw : s.kind = Kind.withdraw := by rw [← hspec.2.1]; exact hkind
      have hle : na.qty ≤ s.capacity := hspec.2.2.2 (by rw [hkw]; decide)
      have hpos : 1 ≤ na.qty := hspec.2.2.1
      have hcap : s.capacity ≤ bank item := hwf item s hmem hkw
      rw [hspec.1]; omega
  | succ n ih =>
    intro result h hkind
    simp only [nextHelper] at h
    cases hfs : firstStep item (need - owned item) owned (sources item) with
    | some na =>
      simp only [hfs] at h; subst h
      obtain ⟨s, hmem, _, hstep⟩ := firstStep_spec item (need - owned item) owned _ _ hfs
      have hspec := stepFor_some hstep
      have hkw : s.kind = Kind.withdraw := by rw [← hspec.2.1]; exact hkind
      have hle : na.qty ≤ s.capacity := hspec.2.2.2 (by rw [hkw]; decide)
      have hpos : 1 ≤ na.qty := hspec.2.2.1
      have hcap : s.capacity ≤ bank item := hwf item s hmem hkw
      rw [hspec.1]; omega
    | none =>
      simp only [hfs] at h
      split at h
      · subst h; simp at hkind
      · split at h
        · rename_i p _
          split at h
          · exact ih p.1 (p.2 * (need - owned item)) result h hkind
          · rename_i hbank
            subst h
            exact Nat.pos_of_ne_zero hbank
        · subst h; simp at hkind

/-- **WITHDRAW-LE-BANK.** A `withdraw` never asks for more than the bank holds. -/
theorem nextHelper_withdraw_le_bank
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned   : String → Nat)
    (bank    : String → Nat)
    (hwf     : WFWithdraw sources bank) :
    ∀ (item : String) (need fuel : Nat) (result : NextAction),
      nextHelper recipes sources owned bank item need fuel = result →
      result.kind = Kind.withdraw →
      result.qty ≤ bank result.item := by
  intro item need fuel
  induction fuel generalizing item need with
  | zero =>
    intro result h hkind
    simp only [nextHelper] at h
    cases hfs : firstStep item (need - owned item) owned (sources item) with
    | none => simp only [hfs, Option.getD_none] at h; subst h; simp at hkind
    | some na =>
      simp only [hfs, Option.getD_some] at h; subst h
      obtain ⟨s, hmem, _, hstep⟩ := firstStep_spec item (need - owned item) owned _ _ hfs
      have hspec := stepFor_some hstep
      have hkw : s.kind = Kind.withdraw := by rw [← hspec.2.1]; exact hkind
      have hle : na.qty ≤ s.capacity := hspec.2.2.2 (by rw [hkw]; decide)
      have hcap : s.capacity ≤ bank item := hwf item s hmem hkw
      rw [hspec.1]; omega
  | succ n ih =>
    intro result h hkind
    simp only [nextHelper] at h
    cases hfs : firstStep item (need - owned item) owned (sources item) with
    | some na =>
      simp only [hfs] at h; subst h
      obtain ⟨s, hmem, _, hstep⟩ := firstStep_spec item (need - owned item) owned _ _ hfs
      have hspec := stepFor_some hstep
      have hkw : s.kind = Kind.withdraw := by rw [← hspec.2.1]; exact hkind
      have hle : na.qty ≤ s.capacity := hspec.2.2.2 (by rw [hkw]; decide)
      have hcap : s.capacity ≤ bank item := hwf item s hmem hkw
      rw [hspec.1]; omega
    | none =>
      simp only [hfs] at h
      split at h
      · subst h; simp at hkind
      · split at h
        · rename_i p _
          split at h
          · exact ih p.1 (p.2 * (need - owned item)) result h hkind
          · subst h
            exact Nat.min_le_left _ _
        · subst h; simp at hkind

/-- **ENTRY-LEVEL WITHDRAW-BANKED.** Lifts `nextHelper_withdraw_banked` through
`nextCraftTarget`, pinning the withdraw safety at the public API. -/
theorem nextCraftTarget_withdraw_banked
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned bank : String → Nat)
    (hwf : WFWithdraw sources bank)
    (target : String) (qty fuel : Nat)
    (result : NextAction)
    (h : nextCraftTarget recipes sources owned bank target qty fuel = some result)
    (hk : result.kind = Kind.withdraw) :
    0 < bank result.item := by
  simp only [nextCraftTarget] at h
  split at h
  · simp at h
  · simp only [Option.some.injEq] at h
    subst h
    exact nextHelper_withdraw_banked recipes sources owned bank hwf target qty fuel _ rfl hk

/-! ## Non-vacuity witnesses — copper_ring chain -/

/-
copper_ring recipe:
  copper_ring: 1 × copper_bar
  copper_bar:  10 × copper_ore
  copper_ore:  raw (gather)
-/

private def copperRecipes : String → Option (List (String × Nat))
  | "copper_ring" => some [("copper_bar", 1)]
  | "copper_bar"  => some [("copper_ore", 10)]
  | _             => none

private def noSources : String → List Source := fun _ => []
private def ownedZero : String → Nat := fun _ => 0
private def bankZero  : String → Nat := fun _ => 0

-- With 0 owned and empty bank, first action is gather copper_ore (30 needed).
example : nextCraftTarget copperRecipes noSources ownedZero bankZero "copper_ring" 3 10 =
    some ⟨"copper_ore", .gather, 30, ""⟩ := by decide

-- With 30 ore, next action is craft copper_bar (deficit = 3).
private def owned30ore : String → Nat
  | "copper_ore" => 30
  | _ => 0

example : nextCraftTarget copperRecipes noSources owned30ore bankZero "copper_ring" 3 10 =
    some ⟨"copper_bar", .craft, 3, ""⟩ := by decide

-- With 30 ore + 3 bars, next action is craft copper_ring (deficit = 3).
private def owned30ore3bar : String → Nat
  | "copper_ore" => 30
  | "copper_bar" => 3
  | _ => 0

example : nextCraftTarget copperRecipes noSources owned30ore3bar bankZero "copper_ring" 3 10 =
    some ⟨"copper_ring", .craft, 3, ""⟩ := by decide

-- Already satisfied → none.
private def owned3ring : String → Nat
  | "copper_ring" => 3
  | _ => 0

example : nextCraftTarget copperRecipes noSources owned3ring bankZero "copper_ring" 3 10 = none := by decide

-- WITHDRAW non-vacuity: 0 owned but 5 copper_bar in the bank ⇒ withdraw copper_bar (min 5 3 = 3).
private def bankCopperBar : String → Nat
  | "copper_bar" => 5
  | _ => 0

example : nextCraftTarget copperRecipes noSources ownedZero bankCopperBar "copper_ring" 3 10 =
    some ⟨"copper_bar", .withdraw, 3, ""⟩ := by decide

-- WITHDRAW-BANKED non-vacuity: the withdrawn item is genuinely banked.
example : 0 < bankCopperBar "copper_bar" := by decide

-- ORDERING non-vacuity: craft returned for copper_bar at owned30ore ⇒ inputs satisfied.
example : ∃ inputs,
    copperRecipes "copper_bar" = some inputs ∧
    inputs.find? (fun p => decide (owned30ore p.1 < p.2 * 3)) = none := by decide

-- SHORTNESS non-vacuity: qty ≥ 1 in a non-none case.
example : 1 ≤ (nextCraftTarget copperRecipes noSources ownedZero bankZero "copper_ring" 3 10).get!.qty := by decide

/-! ### Widened-source non-vacuity — RECYCLE / BUY / DROP genuinely fire. -/

-- A RECYCLE source for copper_bar (destroy `copper_dagger`, yield 2 per, capacity
-- 8, 4 daggers owned ⇒ live bound 8). Target 3 rings needs 3 bars → recycle emits
-- min(3, 8, 8) = 3, debiting copper_dagger.
private def recycleBarSources : String → List Source
  | "copper_bar" => [⟨.recycle, "copper_dagger", 2, 8⟩]
  | _            => []

private def owned30ore4dagger : String → Nat
  | "copper_ore"    => 30
  | "copper_dagger" => 4
  | _ => 0

example : nextCraftTarget copperRecipes recycleBarSources owned30ore4dagger bankZero "copper_ring" 3 10 =
    some ⟨"copper_bar", .recycle, 3, "copper_dagger"⟩ := by decide

-- RECYCLE live-bound non-vacuity: only 1 dagger owned ⇒ live cap min(3, 8, 2) = 2.
private def owned30ore1dagger : String → Nat
  | "copper_ore"    => 30
  | "copper_dagger" => 1
  | _ => 0

example : nextCraftTarget copperRecipes recycleBarSources owned30ore1dagger bankZero "copper_ring" 3 10 =
    some ⟨"copper_bar", .recycle, 2, "copper_dagger"⟩ := by decide

-- BUY source for a raw-ish item: copper_ore bought from npc `smith`.
private def buyOreSources : String → List Source
  | "copper_ore" => [⟨.buy, "smith", 1, 1000000000⟩]
  | _            => []

example : nextCraftTarget copperRecipes buyOreSources ownedZero bankZero "copper_ring" 3 10 =
    some ⟨"copper_ore", .buy, 30, "smith"⟩ := by decide

-- DROP source: copper_ore dropped by monster `mole`.
private def dropOreSources : String → List Source
  | "copper_ore" => [⟨.drop, "mole", 1, 1000000000⟩]
  | _            => []

example : nextCraftTarget copperRecipes dropOreSources ownedZero bankZero "copper_ring" 3 10 =
    some ⟨"copper_ore", .drop, 30, "mole"⟩ := by decide

-- CRAFT source defers to the recipe descent (break): a CRAFT source for
-- copper_bar does NOT short-circuit; the descent still gathers ore first.
private def craftBarSources : String → List Source
  | "copper_bar" => [⟨.craft, "copper_bar", 1, 1000000000⟩]
  | _            => []

example : nextCraftTarget copperRecipes craftBarSources ownedZero bankZero "copper_ring" 3 10 =
    some ⟨"copper_ore", .gather, 30, ""⟩ := by decide

end Formal.NextCraftAction
