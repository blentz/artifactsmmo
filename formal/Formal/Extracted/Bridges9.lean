import Formal.StrategicValue
import Formal.Extracted.StrategicValue

/-!
# Extracted.Bridges (StrategicValue)

Ties the extracted `Extracted.StrategicValue.strategic_value_pure` (flat int
args, byte-identical to `tiers/strategic_value.py` via the drift gate) to the
hand model `Formal.StrategicValue.strategicValue`, then TRANSFERS the
nonnegativity and per-stat monotonicity contracts onto the extracted def so the
proved properties hold of the exact arithmetic the Python core runs.
-/

namespace Extracted.Bridges

open Formal.StrategicValue

/-- The extracted flat-arg core equals the hand structured model, ∀ inputs. -/
theorem strategic_value_bridge
    (combatRaw wisdom prospecting inventorySpace haste
     combatW wisdomW prospectingW inventoryW hasteW : Int) :
    Extracted.StrategicValue.strategic_value_pure
        combatRaw wisdom prospecting inventorySpace haste
        combatW wisdomW prospectingW inventoryW hasteW
      = strategicValue
        ⟨combatRaw, wisdom, prospecting, inventorySpace, haste⟩
        ⟨combatW, wisdomW, prospectingW, inventoryW, hasteW⟩ := by
  unfold Extracted.StrategicValue.strategic_value_pure strategicValue
  rfl

/-- TRANSFERRED (`strategicValue_nonneg`): nonneg stats and nonneg weights give
a nonneg extracted score (the ObjectiveGap gap-bound precondition). -/
theorem strategic_value_nonneg_extracted
    (combatRaw wisdom prospecting inventorySpace haste
     combatW wisdomW prospectingW inventoryW hasteW : Int)
    (hcr : 0 ≤ combatRaw) (hwi : 0 ≤ wisdom) (hpr : 0 ≤ prospecting)
    (his : 0 ≤ inventorySpace) (hha : 0 ≤ haste)
    (hwc : 0 ≤ combatW) (hww : 0 ≤ wisdomW) (hwp : 0 ≤ prospectingW)
    (hwiv : 0 ≤ inventoryW) (hwh : 0 ≤ hasteW) :
    0 ≤ Extracted.StrategicValue.strategic_value_pure
        combatRaw wisdom prospecting inventorySpace haste
        combatW wisdomW prospectingW inventoryW hasteW := by
  rw [strategic_value_bridge]
  exact strategicValue_nonneg _ _ hcr hwi hpr his hha hwc hww hwp hwiv hwh

/-- TRANSFERRED (`strategicValue_mono_combatRaw`). -/
theorem strategic_value_mono_combatRaw_extracted
    (combatRaw wisdom prospecting inventorySpace haste
     combatW wisdomW prospectingW inventoryW hasteW c' : Int)
    (hw : 0 ≤ combatW) (h : combatRaw ≤ c') :
    Extracted.StrategicValue.strategic_value_pure
        combatRaw wisdom prospecting inventorySpace haste
        combatW wisdomW prospectingW inventoryW hasteW
      ≤ Extracted.StrategicValue.strategic_value_pure
        c' wisdom prospecting inventorySpace haste
        combatW wisdomW prospectingW inventoryW hasteW := by
  rw [strategic_value_bridge, strategic_value_bridge]
  exact strategicValue_mono_combatRaw _ _ c' hw h

/-- TRANSFERRED (`strategicValue_mono_wisdom`). -/
theorem strategic_value_mono_wisdom_extracted
    (combatRaw wisdom prospecting inventorySpace haste
     combatW wisdomW prospectingW inventoryW hasteW x' : Int)
    (hw : 0 ≤ wisdomW) (h : wisdom ≤ x') :
    Extracted.StrategicValue.strategic_value_pure
        combatRaw wisdom prospecting inventorySpace haste
        combatW wisdomW prospectingW inventoryW hasteW
      ≤ Extracted.StrategicValue.strategic_value_pure
        combatRaw x' prospecting inventorySpace haste
        combatW wisdomW prospectingW inventoryW hasteW := by
  rw [strategic_value_bridge, strategic_value_bridge]
  exact strategicValue_mono_wisdom _ _ x' hw h

/-- TRANSFERRED (`strategicValue_mono_prospecting`). -/
theorem strategic_value_mono_prospecting_extracted
    (combatRaw wisdom prospecting inventorySpace haste
     combatW wisdomW prospectingW inventoryW hasteW x' : Int)
    (hw : 0 ≤ prospectingW) (h : prospecting ≤ x') :
    Extracted.StrategicValue.strategic_value_pure
        combatRaw wisdom prospecting inventorySpace haste
        combatW wisdomW prospectingW inventoryW hasteW
      ≤ Extracted.StrategicValue.strategic_value_pure
        combatRaw wisdom x' inventorySpace haste
        combatW wisdomW prospectingW inventoryW hasteW := by
  rw [strategic_value_bridge, strategic_value_bridge]
  exact strategicValue_mono_prospecting _ _ x' hw h

/-- TRANSFERRED (`strategicValue_mono_inventorySpace`). -/
theorem strategic_value_mono_inventorySpace_extracted
    (combatRaw wisdom prospecting inventorySpace haste
     combatW wisdomW prospectingW inventoryW hasteW x' : Int)
    (hw : 0 ≤ inventoryW) (h : inventorySpace ≤ x') :
    Extracted.StrategicValue.strategic_value_pure
        combatRaw wisdom prospecting inventorySpace haste
        combatW wisdomW prospectingW inventoryW hasteW
      ≤ Extracted.StrategicValue.strategic_value_pure
        combatRaw wisdom prospecting x' haste
        combatW wisdomW prospectingW inventoryW hasteW := by
  rw [strategic_value_bridge, strategic_value_bridge]
  exact strategicValue_mono_inventorySpace _ _ x' hw h

/-- TRANSFERRED (`strategicValue_mono_haste`). -/
theorem strategic_value_mono_haste_extracted
    (combatRaw wisdom prospecting inventorySpace haste
     combatW wisdomW prospectingW inventoryW hasteW x' : Int)
    (hw : 0 ≤ hasteW) (h : haste ≤ x') :
    Extracted.StrategicValue.strategic_value_pure
        combatRaw wisdom prospecting inventorySpace haste
        combatW wisdomW prospectingW inventoryW hasteW
      ≤ Extracted.StrategicValue.strategic_value_pure
        combatRaw wisdom prospecting inventorySpace x'
        combatW wisdomW prospectingW inventoryW hasteW := by
  rw [strategic_value_bridge, strategic_value_bridge]
  exact strategicValue_mono_haste _ _ x' hw h

end Extracted.Bridges
