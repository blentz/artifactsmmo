import Formal.Liveness.GameDataFixture
import Formal.CombatTargetExistence
import Formal.Liveness.GearTierLeveling
import Formal.FightOdds
import Mathlib.Tactic

/-! # WinnableGrounded — kernel-prove `WinnableAcrossBand` over the live catalog

`Formal/Liveness/GearTierLeveling.lean` leaves `WinnableAcrossBand` as the
gear-tier winnability HYPOTHESIS that grounds the leveling loop: at every band
level `1 ≤ L < 50` the live monster catalog contains a winnable, XP-positive,
not-overleveled monster. This module DISCHARGES that hypothesis against the
extracted live catalog, kernel-checked.

## What is proven in the kernel vs. pinned by differential

* The combat VERDICT is production's fight odds (spec 2026-10-15
  fight-gates-odds §1/§5): `predict_win` is `P(win) ≥ θ` over the exact ending
  distribution `Formal.FightOdds.fightOdds` (differential-locked to production
  `fight_odds_core.fight_odds` by `formal/diff/test_fight_odds_diff.py`). Deciding
  `fightOdds` itself is infeasible (an unmerged 4^rounds tree), so each row is
  decided IN KERNEL on its counted-crit floor `Formal.FightOdds.critBound`: one
  no-stock path (the player never crits, the monster crits its first
  `critBudget` turns) and a binomial table. `witnessTheta ≤ critBound` is
  `decide +kernel`d per row, and `Formal.FightOdds.winProb_ge_critBound` (proved
  for every input, any stock) lifts it to `θ ≤ winProb (fightOdds …)` for every
  θ ≤ `witnessTheta` (`rowWinnable_sound`). The old closed form
  (`Formal.PredictWin.predictWin`) is no longer the verdict; its scalars stay in
  the rows only for the projection pin.

* The messy loadout PROJECTION and fight SPLIT (base stats + summed item stats →
  the `Terms`/`Damage`/HP/restore the odds take) are computed in PYTHON by the
  real production chain (`pick_loadout` + `project_loadout_stats` +
  `combat.fight_split` / `fight_max_hp` / `worn_restore`) and emitted into
  `winnableWitness` (`GameDataFixture.lean`). Their fidelity to production is
  pinned by `formal/diff/test_winnable_witness_diff.py`, which re-derives each
  row from production, asserts production `is_winnable` is True and the Python
  mirror of `critBound` is ≥ 99/100. The kernel trusts the scalars only as far as
  that differential enforces them — the witness is never hand-massaged. The
  `critBudget` certificate is NOT trusted: any budget gives a sound floor.

* Loadout OBTAINABILITY: every witness loadout item has `level ≤ L` (asserted by
  the same differential), and that an obtainable loadout is reachable in the
  planner is Task 3's proven `canonicalPlan` obtainability
  (`gear_obtainable_of_perActionLength_le` in `PlanModel.lean`).

So the witness table is production-faithful by construction+differential, and
THIS module verifies, purely in the kernel, that the witness witnesses
`WinnableAcrossBand` at every band level.

Liveness-tier (imports Mathlib). NO new axioms beyond the standard set + LIV-001
carried by the imports; the band-reduction lemma is `decide`/`omega`, the
per-row verdict is `decide +kernel` over exact `Rat` arithmetic (no
`native_decide`).
-/

set_option maxRecDepth 100000

namespace Formal.Liveness.WinnableGrounded

open Formal.CombatTargetExistence
open Formal.Liveness
open Formal.Liveness.GearTierLeveling
open Formal.Liveness.GameDataFixture
open Formal.PredictWin

/-- The P(win) every witness row is proved to reach. Liveness holds for any
character threshold θ ≤ 99/100 (`rowWinnable_sound`,
`winnableAcrossBand_at_threshold`) — a HYPOTHESIS, not a production invariant:
`win_threshold_core` never caps θ (USER 2026-10-16: keep θ as derived), and a
learned θ = t_loss / (t_win + t_loss) exceeds 0.99 when a loss costs more than
99 wins. `combat-loadout-report` names every (character, monster) above it.
Python mirror: `win_threshold_core.LIVENESS_THETA`. -/
def witnessTheta : Rat := 99 / 100

/-- The row's fight-odds `Terms` (production `fight_split`'s terms). -/
def rowTerms (r : WitnessRow) : Formal.FightOutcome.Terms :=
  { rawPlayer := r.tRawPlayer, killStep := r.tKillStep, monsterHp := r.tMonsterHp,
    recon := r.tRecon, dieStep := r.tDieStep, playerFirst := r.tPlayerFirst }

/-- The row's round `Damage` at its real crit chances (production `fight_split`). -/
def rowDamage (r : WitnessRow) : Formal.FightOdds.Damage :=
  { monsterHp := r.dMonsterHp, killNormal := r.dKillNormal, killCrit := r.dKillCrit,
    pCrit := r.dPCrit, dieNormal := r.dDieNormal, dieCrit := r.dDieCrit, mCrit := r.dMCrit,
    burn := r.dBurn }

/-- The row's fight odds: from its start HP, at its max HP, with its worn restore. -/
def rowOdds (r : WitnessRow) : List (Rat × Formal.FightOdds.Ending) :=
  Formal.FightOdds.fightOdds (rowTerms r) (rowDamage r) r.fightHp r.fightMaxHp r.restore r.stock

/-- The row's proved floor on P(win) (`Formal.FightOdds.critBound` at its crit budget). -/
def rowBound (r : WitnessRow) : Rat :=
  Formal.FightOdds.critBound (rowTerms r) (rowDamage r) r.fightHp r.fightMaxHp r.critBudget

/-- The winnability verdict for a witness row: the floor's side conditions and
`witnessTheta ≤ rowBound`, all decidable over the row's exact scalars. -/
def rowWinnable (r : WitnessRow) : Bool :=
  decide (r.dKillNormal ≤ r.dKillCrit) && decide (r.dDieNormal ≤ r.dDieCrit)
    && decide (r.dPCrit ≤ 100) && decide (r.dMCrit ≤ 100) && decide (witnessTheta ≤ rowBound r)

/-- A winnable row's fight is won with probability at least any θ ≤
`witnessTheta`, at the row's real crit chances and stock — so production's
`predict_win` (`P(win) ≥ θ`) holds for the row at every such threshold. -/
theorem rowWinnable_sound (r : WitnessRow) (h : rowWinnable r = true) (θ : Rat)
    (hθ : θ ≤ witnessTheta) : θ ≤ Formal.FightOdds.winProb (rowOdds r) := by
  simp only [rowWinnable, Bool.and_eq_true, decide_eq_true_eq] at h
  obtain ⟨⟨⟨⟨hk, hd⟩, hp⟩, hm⟩, hb⟩ := h
  exact le_trans hθ (le_trans hb (Formal.FightOdds.winProb_ge_critBound _ _ _ _ _ _ _ hk hd hp hm))

/-- The witness catalog as abstract `Monster`s: one entry per witness row, the
`code` a stable row index, the `level` the row's winning monster level. Every
entry is a real live-catalog monster (the witness rows come from the production
sweep over `monsterCatalog`). -/
def catalogAsMonsters : List Monster :=
  (winnableWitness.zipIdx).map (fun (r, i) => { code := (i : Int), level := r.monsterLevel })

/-- Winnability predicate over `catalogAsMonsters`: look up the witness row by
the monster's code-index and `decide` the kernel `predictWin` verdict. -/
def winnableConcrete : WinnableFn := fun m =>
  match winnableWitness[m.code.toNat]? with
  | some r => rowWinnable r
  | none => false

/-- XP-positivity over `catalogAsMonsters`. Every witness row is, by
construction, the XP-positive winner the production picker chose (the witness
builder filters on `xp_per_kill > 0`, differential-pinned), so a monster present
in the witness catalog is XP-positive. -/
def xpPosConcrete : WinnableFn := fun m =>
  match winnableWitness[m.code.toNat]? with
  | some _ => true
  | none => false

/-- The abstract monster carried by witness row `i` in `catalogAsMonsters`. -/
def witnessMonster (r : WitnessRow) (i : Nat) : Monster :=
  { code := (i : Int), level := r.monsterLevel }

/-- Per-row band witness, stated over the SAME `winnableConcrete`/`xpPosConcrete`
/`notOverleveled` the theorem uses, so the single `decide` also closes the
witness↔catalog binding. Checks: the rows are in level order (`r.level = i+1`),
and at the row's own level the row's monster is winnable, XP-positive, and not
overleveled. -/
def rowWitnessesBand (r : WitnessRow) (i : Nat) : Bool :=
  decide (r.level = (i : Int) + 1)
    && winnableConcrete (witnessMonster r i)
    && xpPosConcrete (witnessMonster r i)
    && notOverleveled r.level (witnessMonster r i)

/-- Every witness row witnesses its own band condition — the single `decide`
over the 49-row table. The per-row `critBound` over the 49 rows is a finite,
fully-determined evaluation (exact `Int`/`Rat` arithmetic, no `Float`, no
`Classical`); we discharge it by `decide +kernel` (no `native_decide`, so no
`Lean.ofReduceBool` axiom is introduced). -/
theorem all_rows_witness_band :
    (winnableWitness.zipIdx.all (fun (r, i) => rowWitnessesBand r i)) = true := by
  decide +kernel


/-- Membership-aware extraction: every entry of `winnableWitness.zipIdx` satisfies
`rowWitnessesBand`. -/
theorem rowWitnessesBand_of_mem (r : WitnessRow) (i : Nat)
    (h : (r, i) ∈ winnableWitness.zipIdx) :
    rowWitnessesBand r i = true := by
  have hall := all_rows_witness_band
  rw [List.all_eq_true] at hall
  exact hall (r, i) h

/-- Every witness row's fight is won with probability at least any θ ≤
`witnessTheta` — the odds verdict production's `predict_win` reads. -/
theorem witness_rows_win (r : WitnessRow) (hr : r ∈ winnableWitness) (θ : Rat)
    (hθ : θ ≤ witnessTheta) : θ ≤ Formal.FightOdds.winProb (rowOdds r) := by
  obtain ⟨i, hi⟩ := List.mem_iff_getElem.mp hr
  obtain ⟨hlt, rfl⟩ := hi
  have hmem : (winnableWitness[i], i) ∈ winnableWitness.zipIdx :=
    List.mem_zipIdx_iff_getElem?.mpr (List.getElem?_eq_getElem hlt)
  have hband := rowWitnessesBand_of_mem _ _ hmem
  unfold rowWitnessesBand winnableConcrete witnessMonster at hband
  simp only [Bool.and_eq_true] at hband
  have hw := hband.1.1.2
  simp only [Int.toNat_natCast, List.getElem?_eq_getElem hlt] at hw
  exact rowWinnable_sound _ hw θ hθ

/-! ## The grounded theorem. -/

/-- **`WinnableAcrossBand` discharged over the live catalog.** At every band
level `1 ≤ L < 50` the witness catalog contains a winnable, XP-positive,
not-overleveled monster — the witness row whose `level = L`. The winnability is
the kernel-decided counted-crit floor over production's fight split
(differential-pinned), which by `rowWinnable_sound` gives P(win) ≥ θ for every
θ ≤ `witnessTheta` — a faithful grounding of the gear-tier hypothesis on the
odds verdict, not a re-derivation of `pick_loadout`. -/
theorem winnableAcrossBand_grounded :
    WinnableAcrossBand winnableConcrete xpPosConcrete catalogAsMonsters := by
  intro L hL
  -- The witness row witnessing L sits at index L.toNat - 1 (rows in level order).
  obtain ⟨hlo, hhi⟩ := hL
  set i : Nat := L.toNat - 1 with hi
  -- Index i is in range (0 ≤ i < 49 = length).
  have hlen : winnableWitness.length = 49 := by decide
  have hirange : i < winnableWitness.length := by rw [hlen, hi]; omega
  -- The membership of (row, i) in zipIdx.
  have hmem : (winnableWitness[i]'hirange, i) ∈ winnableWitness.zipIdx :=
    List.mem_zipIdx_iff_getElem?.mpr (List.getElem?_eq_getElem hirange)
  have hband := rowWitnessesBand_of_mem _ _ hmem
  -- Unpack the conjunction.
  unfold rowWitnessesBand at hband
  simp only [Bool.and_eq_true, decide_eq_true_eq] at hband
  obtain ⟨⟨⟨hlvl, hwin⟩, hxp⟩, hnotover⟩ := hband
  -- The witness monster is the existential.
  refine ⟨witnessMonster (winnableWitness[i]'hirange) i, ?_, hwin, hxp, ?_⟩
  · -- membership in catalogAsMonsters.
    unfold catalogAsMonsters witnessMonster
    rw [List.mem_map]
    exact ⟨(winnableWitness[i]'hirange, i),
      List.mem_zipIdx_iff_getElem?.mpr (List.getElem?_eq_getElem hirange), rfl⟩
  · -- notOverleveled L m: r.level = i+1 = L, and the row is not overleveled at r.level.
    have hLeq : (i : Int) + 1 = L := by rw [hi]; omega
    unfold notOverleveled witnessMonster at hnotover ⊢
    rw [decide_eq_true_eq] at hnotover ⊢
    -- hnotover : monsterLevel ≤ r.level + 2, hlvl : r.level = i+1, hLeq : i+1 = L.
    rw [hlvl, hLeq] at hnotover
    omega

/-- **The grounding stated at production's verdict, with its hypothesis
explicit.** For every character threshold θ ≤ `witnessTheta`, every band level
`1 ≤ L < 50` has a witness row at level `L` whose fight production's
`predict_win` takes: θ ≤ P(win). Production does not enforce `θ ≤ witnessTheta`
(see `witnessTheta`); a pair above it is outside this theorem. -/
theorem winnableAcrossBand_at_threshold (θ : Rat) (hθ : θ ≤ witnessTheta)
    (L : Int) (hL : 1 ≤ L ∧ L < 50) :
    ∃ r ∈ winnableWitness, r.level = L ∧ θ ≤ Formal.FightOdds.winProb (rowOdds r) := by
  obtain ⟨hlo, hhi⟩ := hL
  set i : Nat := L.toNat - 1 with hi
  have hlen : winnableWitness.length = 49 := by decide
  have hirange : i < winnableWitness.length := by rw [hlen, hi]; omega
  have hmem : (winnableWitness[i]'hirange, i) ∈ winnableWitness.zipIdx :=
    List.mem_zipIdx_iff_getElem?.mpr (List.getElem?_eq_getElem hirange)
  have hband := rowWitnessesBand_of_mem _ _ hmem
  unfold rowWitnessesBand at hband
  simp only [Bool.and_eq_true, decide_eq_true_eq] at hband
  obtain ⟨⟨⟨hlvl, _⟩, _⟩, _⟩ := hband
  refine ⟨winnableWitness[i]'hirange, List.getElem_mem hirange, ?_,
    witness_rows_win _ (List.getElem_mem hirange) θ hθ⟩
  have hLeq : (i : Int) + 1 = L := by rw [hi]; omega
  rw [hlvl, hLeq]

end Formal.Liveness.WinnableGrounded
