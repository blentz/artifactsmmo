-- @concept: items, characters @property: dominance
import Formal.EquipmentScoring
import Formal.GearPolicy

/-!
# Formal.PurposeRouting

**Composition-correctness lemmas for purpose-dispatched equipment selection.**

`EquipmentScoring.pickSlot` is parametric in a score function — it does NOT
say WHICH score function to use for a given task. `PurposeRouting` closes
that gap with three layers:

1. **Combat purpose**: pick maximizes `WScore` against the monster's
   per-element resistance. Pure restatement of the existing Python
   `pick_loadout` for the combat case.

2. **Tool/non-tool tie-break**: when two weapons score equal under
   `WScore`, the user's invariant — "no other correct answer than to go
   from tool to real weapon" — is formalized by a *purpose-augmented
   score* that strictly orders non-tools above tools on ties, while
   preserving every strict `WScore` inequality.

   This is the formal closure of the 2026-06-06 trace bug where
   `fishing_net` (5 water atk, subtype=tool) was picked over
   `wooden_stick` (4 earth atk, subtype=weapon) against zero-resistance
   slimes — `WScore` tied at 5 for the tools and the leftmost won. With
   the augmented score, the tie resolves toward the real combat weapon
   even when both have identical raw WScore, AND any strict WScore win
   still wins.

3. **Gather purpose spec**: pick minimizes the active skill's
   `skill_effects` penalty (more negative = better gather tool). Pure
   specification — the current Python code has NO gather-purpose
   routing; this Lean module is the contract a future Python
   implementation must satisfy.

Closes Phase G2 of `docs/PLAN_composition_correctness.md`.
-/

namespace Formal.PurposeRouting
open Formal.EquipmentScoring

/-! ## Item subtype: tool vs non-tool.

We extend `Item` with an `isTool : Bool` flag that mirrors the Python
`stats.subtype == "tool"` check. `True` means a gather tool (pickaxe /
axe / net) — has `skill_effects` set and is NOT the canonical pick for
combat against a non-resistant target. -/

structure CombatItem where
  base   : Item
  isTool : Bool
deriving Repr, DecidableEq

/-- Lift a per-`CombatItem` projection to the underlying `Item`. -/
@[simp] def liftItem (ci : CombatItem) : Item := ci.base

/-! ## Combat-purpose score: WScore plus non-tool tiebreaker.

The weapon slot's COMBAT term is `rulerScale * WScore + nonToolBonus`. The
`rulerScale` factor — the SAME one every other ruler term carries, see
`EquipmentScoring.rulerScale` — keeps every strict `WScore` inequality strict in
the augmented score (adding `0` or `1` to one side cannot flip a `≥ 2` gap). On
WScore ties the `nonToolBonus` (1 for non-tool, 0 for tool) decides. -/

def nonToolBonus (ci : CombatItem) : Int := if ci.isTool then 0 else 1

@[simp] theorem nonToolBonus_tool (ci : CombatItem) (h : ci.isTool = true) :
    nonToolBonus ci = 0 := by unfold nonToolBonus; simp [h]

@[simp] theorem nonToolBonus_nontool (ci : CombatItem) (h : ci.isTool = false) :
    nonToolBonus ci = 1 := by unfold nonToolBonus; simp [h]

theorem nonToolBonus_nonneg (ci : CombatItem) : 0 ≤ nonToolBonus ci := by
  unfold nonToolBonus
  split <;> decide

theorem nonToolBonus_le_one (ci : CombatItem) : nonToolBonus ci ≤ 1 := by
  unfold nonToolBonus
  split <;> decide

/-- **THE TIE-BREAK IS SUB-QUANTUM.** The bonus is strictly smaller than the
ruler's quantum, which is the whole reason it can decide a tie without ever
disturbing a genuine ordering: every ruler term is a multiple of `rulerScale`,
so two distinct terms differ by at least `rulerScale`, and the bonus moves a
score by at most `rulerScale - 1`. -/
theorem nonToolBonus_lt_rulerScale (ci : CombatItem) : nonToolBonus ci < rulerScale := by
  unfold nonToolBonus rulerScale
  split <;> decide

/-- The weapon slot's COMBAT term: `rulerScale * WScore + nonToolBonus`. -/
def combatScore (monsterRes : ElemStats) (ci : CombatItem) : Int :=
  rulerScale * WScore ci.base monsterRes + nonToolBonus ci

/-! ### The two key combatScore theorems. -/

/-- **Strict WScore preservation**: if WScore strictly orders A above B, the
augmented combat score does too. The `2 *` factor protects against the
`+ 0/1` tiebreaker flipping a strict ordering. -/
theorem combatScore_strict_of_strict_wscore
    (a b : CombatItem) (monsterRes : ElemStats)
    (hStrict : WScore a.base monsterRes < WScore b.base monsterRes) :
    combatScore monsterRes a < combatScore monsterRes b := by
  unfold combatScore rulerScale
  have hAb : 0 ≤ nonToolBonus a := nonToolBonus_nonneg a
  have hAle : nonToolBonus a ≤ 1 := nonToolBonus_le_one a
  have hBb : 0 ≤ nonToolBonus b := nonToolBonus_nonneg b
  have hBle : nonToolBonus b ≤ 1 := nonToolBonus_le_one b
  -- WScore a + 1 ≤ WScore b ⇒ 2*WScore a + 2 ≤ 2*WScore b
  -- 2*WScore a + bonus_a ≤ 2*WScore a + 1 ≤ 2*WScore b - 1 ≤ 2*WScore b + bonus_b - 1
  -- Strict because gap is ≥ 1 from hStrict
  omega

/-- **Tie-break to non-tool**: WScore tie + non-tool beats tool in combat
score. This is the user's invariant for the fishing_net-vs-wooden_stick
case. -/
theorem combatScore_tiebreaks_nontool_over_tool
    (tool nonTool : CombatItem) (monsterRes : ElemStats)
    (hTool    : tool.isTool    = true)
    (hNonTool : nonTool.isTool = false)
    (hTie     : WScore tool.base monsterRes = WScore nonTool.base monsterRes) :
    combatScore monsterRes tool < combatScore monsterRes nonTool := by
  unfold combatScore rulerScale
  rw [hTie]
  have ht := nonToolBonus_tool tool hTool
  have hn := nonToolBonus_nontool nonTool hNonTool
  omega

/-! ## The weapon slot's RULER value: its combat term plus the shared efficiency
term.

`combatScore` above is only HALF the weapon slot's ruler value, exactly as
`EquipmentScoring.ACombat` is only half an armor slot's. The other half is
`EquipmentScoring.AEfficiency` — the SAME function, on the SAME four stats, at
the SAME price — which is what "one ruler" means once a weapon can carry wisdom
or prospecting. Before this, `weapon_score` had no flat-utility block at all and
a weapon's efficiency stats reached no purpose: the four voidstone tools carry
100 prospecting each and obsidian_battleaxe carries `inventory_space = -25`, and
none of it was priced.

Mirrors the Python `equipment/scoring.weapon_score_pure`. -/

/-- The weapon slot's ruler value: combat term + shared efficiency term. -/
def weaponScore (monsterRes : ElemStats) (ci : CombatItem)
    (wisdom prospecting inventorySpace haste : Int) : Int :=
  combatScore monsterRes ci + AEfficiency wisdom prospecting inventorySpace haste

/-- **THE PARTITION, on the weapon slot.** The same statement `AScore_decomp`
makes for armor: the ruler value IS the sum of the two terms the economics layer
weighs, so the acquisition score can neither omit a stat the ruler has nor count
one twice. Definitional. -/
theorem weaponScore_decomp (monsterRes : ElemStats) (ci : CombatItem)
    (wisdom prospecting inventorySpace haste : Int) :
    weaponScore monsterRes ci wisdom prospecting inventorySpace haste
      = combatScore monsterRes ci
        + AEfficiency wisdom prospecting inventorySpace haste := rfl

/-- **A STAT COSTS THE SAME IN EVERY SLOT.** What the four efficiency stats
contribute to a WEAPON's ruler value is literally `AEfficiency` — the term the
armor branch adds — so no stat is priced by which slot happens to carry it. -/
theorem weaponScore_efficiency_eq_AEfficiency (monsterRes : ElemStats) (ci : CombatItem)
    (wisdom prospecting inventorySpace haste : Int) :
    weaponScore monsterRes ci wisdom prospecting inventorySpace haste
        - combatScore monsterRes ci
      = AEfficiency wisdom prospecting inventorySpace haste := by
  unfold weaponScore
  omega

/-- **CROSS-SLOT COMMENSURABILITY.** A weapon whose raw per-turn swing is `d`
natural units and a piece of armor whose defense stops the same `d` natural units
score the SAME ruler combat term, up to the sub-quantum non-tool tie-break. This
is the property the `rulerScale` factor was moved onto the armor terms to buy:
before, the armor side was `1 *` its terms while the weapon side was `2 *`, so
the identical real effect scored half as much on armor.

NOT VACUOUS: `hoff` holds for any armor with `dmg = 0`, `dmgElem = []` and
`crit = 0` (`oTerm _ _ 0 0 = 0`), and `hw`/`ha` are satisfiable simultaneously —
e.g. `d = 0` for a stat-less pair, or a 5-attack weapon against zero resistance
(`WScore = 100000`) against armor whose `Σ monAtk * res` is `500`. -/
theorem ruler_commensurate (ci : CombatItem) (item : Item)
    (monsterAtk monsterRes playerAtk : ElemStats) (d : Int)
    (hw : WScore ci.base monsterRes = d)
    (hoff : (elements.map (fun e => oTerm (elemGet playerAtk e) (elemGet monsterRes e)
              (item.dmg + elemGet item.dmgElem e) item.crit)).sum = 0)
    (ha : 200 * (elements.map (fun e => aTerm (elemGet monsterAtk e)
            (elemGet item.resistance e))).sum = d) :
    combatScore monsterRes ci - nonToolBonus ci
      = ACombat item monsterAtk monsterRes playerAtk 0 := by
  rw [ACombat_defense_only item monsterAtk monsterRes playerAtk hoff, ha]
  unfold combatScore
  rw [hw]
  omega

/-- **The fishing_net invariant on the FULL weapon ruler value.** Two weapons
carrying the same efficiency stats — which is the historical pair exactly
(fishing_net and wooden_stick carry none) — keep the strict `WScore` ordering in
their full ruler values. The efficiency hypothesis is what the ruler genuinely
says: a weapon that is worse at fighting but carries 100 prospecting IS worth
more overall, on the same terms an artifact is, and pursuing it over a better
weapon is prevented one layer up by
`Formal.StrategicValue.pursuit_combat_dominates`, which reads `combatScore`
alone. -/
theorem weaponScore_strict_of_strict_wscore
    (a b : CombatItem) (monsterRes : ElemStats)
    (wisdom prospecting inventorySpace haste : Int)
    (hStrict : WScore a.base monsterRes < WScore b.base monsterRes) :
    weaponScore monsterRes a wisdom prospecting inventorySpace haste
      < weaponScore monsterRes b wisdom prospecting inventorySpace haste := by
  unfold weaponScore
  have h := combatScore_strict_of_strict_wscore a b monsterRes hStrict
  omega

/-- **Tie-break to non-tool on the FULL weapon ruler value.** On a `WScore` tie
with equal efficiency stats the real weapon strictly outranks the tool — the
2026-06-06 fishing_net-over-wooden_stick pick, closed on the score the picker
actually reads. -/
theorem weaponScore_tiebreaks_nontool_over_tool
    (tool nonTool : CombatItem) (monsterRes : ElemStats)
    (wisdom prospecting inventorySpace haste : Int)
    (hTool    : tool.isTool    = true)
    (hNonTool : nonTool.isTool = false)
    (hTie     : WScore tool.base monsterRes = WScore nonTool.base monsterRes) :
    weaponScore monsterRes tool wisdom prospecting inventorySpace haste
      < weaponScore monsterRes nonTool wisdom prospecting inventorySpace haste := by
  unfold weaponScore
  have h := combatScore_tiebreaks_nontool_over_tool tool nonTool monsterRes
    hTool hNonTool hTie
  omega

/-! ## Gather purpose: skill-effect minimization.

A gather tool's effectiveness is encoded as a NEGATIVE skill_effect on its
gathering skill (e.g. copper_pickaxe has `{mining: -10}` meaning 10%
faster mining cooldown). MORE NEGATIVE = better. We model the picker as
minimizing this scalar.

The spec is bare here: we model the integer score and the argmin selection,
then prove the dual of the combat picker. The Python implementation is
the next G2 follow-up commit. -/

/-- Per-item gather score for skill `s`: the (signed) skill_effect on that
skill. The picker wants the MINIMUM (most-negative) value. -/
def gatherScore (skillEffect : Item → Int) (item : Item) : Int :=
  skillEffect item

/-- Gather-purpose argmin: scan the list, keep the leftmost item with the
smallest `gatherScore`. Mirrors a Python `min(candidates, key=score)` with
left-fold tie semantics. -/
def argminBy (score : Item → Int) : Item → List Item → Item
  | best, [] => best
  | best, x :: xs =>
      if score x < score best then argminBy score x xs else argminBy score best xs

/-- The gather picker: `argminBy gatherScore` over feasible candidates. None
when no candidate is feasible. -/
def pickGatherSlot
    (skillEffect : Item → Int) (playerLevel : Int)
    (current : Option Item) (items : List Item) : Option Item :=
  match candidates playerLevel items with
  | [] => current
  | c :: cs =>
      let best := argminBy (gatherScore skillEffect) c cs
      match current with
      | none => some best
      | some curr =>
          if gatherScore skillEffect best < gatherScore skillEffect curr then
            some best
          else
            some curr

/-- Argmin is a member of the input list. -/
theorem argminBy_mem (score : Item → Int) (best : Item) (xs : List Item) :
    argminBy score best xs ∈ best :: xs := by
  induction xs generalizing best with
  | nil => simp [argminBy]
  | cons y ys ih =>
    simp only [argminBy]
    split
    · -- score y < score best ⇒ recurse with y as new best
      have hMem := ih y
      rw [List.mem_cons] at hMem
      rcases hMem with hEq | hTail
      · rw [hEq]; exact List.mem_cons_of_mem _ (List.mem_cons_self)
      · exact List.mem_cons_of_mem _ (List.mem_cons_of_mem _ hTail)
    · -- not strictly less ⇒ recurse with best unchanged
      have hMem := ih best
      rw [List.mem_cons] at hMem
      rcases hMem with hEq | hTail
      · rw [hEq]; exact List.mem_cons_self
      · exact List.mem_cons_of_mem _ (List.mem_cons_of_mem _ hTail)

/-- Argmin is a lower bound for the input list. -/
theorem argminBy_le (score : Item → Int) (best : Item) (xs : List Item) :
    ∀ x ∈ best :: xs, score (argminBy score best xs) ≤ score x := by
  induction xs generalizing best with
  | nil =>
    intro x hx
    cases hx with
    | head => simp [argminBy]
    | tail _ h => nomatch h
  | cons y ys ih =>
    intro x hx
    simp only [argminBy]
    split
    next hlt =>
      -- recursive case with new best = y
      have hIH := ih y
      cases hx with
      | head =>
        -- x = best (original); show score (argmin y ys) ≤ score best
        have hAuxRec : score (argminBy score y ys) ≤ score y := hIH y (List.Mem.head _)
        omega
      | tail _ hx2 =>
        cases hx2 with
        | head => exact hIH y (List.Mem.head _)
        | tail _ hRest => exact hIH x (List.Mem.tail _ hRest)
    next hge =>
      have hIH := ih best
      cases hx with
      | head => exact hIH best (List.Mem.head _)
      | tail _ hx2 =>
        cases hx2 with
        | head =>
          -- x = y; need score (argmin best ys) ≤ score y
          have hBestLeY : score best ≤ score y := by omega
          have hAuxBest : score (argminBy score best ys) ≤ score best :=
            hIH best (List.Mem.head _)
          omega
        | tail _ hRest => exact hIH x (List.Mem.tail _ hRest)

/-- **Gather-purpose optimality**: the picked item minimizes `gatherScore`
over all feasible candidates. The dual of `argmaxBy_is_max`. -/
theorem pickGatherSlot_score_optimal
    (skillEffect : Item → Int) (playerLevel : Int)
    (items : List Item)
    (picked : Item)
    (hPick : pickGatherSlot skillEffect playerLevel none items = some picked) :
    ∀ c ∈ candidates playerLevel items,
        gatherScore skillEffect picked ≤ gatherScore skillEffect c := by
  unfold pickGatherSlot at hPick
  cases hC : candidates playerLevel items with
  | nil =>
    rw [hC] at hPick
    simp at hPick
  | cons hd tl =>
    rw [hC] at hPick
    simp at hPick
    intro x hx
    have hLe := argminBy_le (gatherScore skillEffect) hd tl x hx
    rw [hPick.symm]
    exact hLe

/-! ## Composition theorem: the user's fishing_net invariant in Lean.

Suppose Robby owns two weapons that score identically under `WScore`
against a target — one a tool (fishing_net), the other a non-tool
(wooden_stick). With the augmented `combatScore`, the picker MUST pick
the non-tool. -/

/-- CombatItem-typed argmax: scan the list, swap on strictly higher combat
score. Mirrors `EquipmentScoring.argmaxBy` but at the `CombatItem` level
because the augmented score is purpose-typed. -/
def argmaxByC (score : CombatItem → Int) : CombatItem → List CombatItem → CombatItem
  | best, [] => best
  | best, x :: xs =>
      if score x > score best then argmaxByC score x xs else argmaxByC score best xs

theorem combat_picks_nontool_over_tied_tool
    (tool nonTool : CombatItem) (monsterRes : ElemStats)
    (hTool    : tool.isTool    = true)
    (hNonTool : nonTool.isTool = false)
    (hTie     : WScore tool.base monsterRes = WScore nonTool.base monsterRes) :
    argmaxByC (combatScore monsterRes) tool [nonTool] = nonTool := by
  unfold argmaxByC
  have hStrict : combatScore monsterRes tool < combatScore monsterRes nonTool :=
    combatScore_tiebreaks_nontool_over_tool tool nonTool monsterRes hTool hNonTool hTie
  simp [hStrict, argmaxByC]

end Formal.PurposeRouting
