-- @concept: items, characters @property: safety, monotonicity
/-
Formal model of the gear-review latch transition mirroring
`src/artifactsmmo_cli/ai/gear_latch.py::GearLatch.update`:

THE CODE FACTS this mirrors (gear_latch.py):
  * `triggered = state.level > prev_level or last_outcome == "error:fight_lost"`
    — the latch is TRIGGERED on a level-up OR a predicted-winnable fight loss.
  * `if triggered: self._active = True` — a trigger forces the latch ON.
  * `if self._active and not has_craftable_upgrade_any_slot(...): self._active
    = False` — the latch CLEARS the moment no craftable upgrade remains, even if
    it was just triggered (clear dominates).
  * otherwise the latch HOLDS its prior `_active` value.

Modeled as a single Bool step over four flags:
  * `active`     — the latch's prior value (`self._active` on entry),
  * `leveledUp`  — `state.level > prev_level`,
  * `loss`       — `last_outcome == "error:fight_lost"`,
  * `hasUpgrade` — `has_craftable_upgrade_any_slot(state, game_data)`.

These are finite Bool facts — proved by `decide` / Bool case analysis.

Lean core only — no mathlib.
-/

namespace Formal.GearLatch

/-- One latch transition. `t` is the post-trigger intermediate value
(`active ∨ leveledUp ∨ loss`); if it is set but no craftable upgrade remains the
latch clears, else it takes `t`. Mirrors `GearLatch.update` exactly. -/
def step (active leveledUp loss hasUpgrade : Bool) : Bool :=
  let t := active || leveledUp || loss
  if t && !hasUpgrade then false else t

/-! ### Role theorems. -/

/-- **SET ON LEVEL-UP.** A level-up with a craftable upgrade available sets the
latch ON, regardless of the prior value or fight outcome. -/
theorem set_on_levelup (active loss hasUpgrade : Bool)
    (hlvl : leveledUp = true) (hup : hasUpgrade = true) :
    step active leveledUp loss hasUpgrade = true := by
  subst hlvl; subst hup; cases active <;> cases loss <;> rfl

/-- **SET ON LOSS.** A predicted-winnable fight loss with a craftable upgrade
available sets the latch ON, regardless of the prior value or level change. -/
theorem set_on_loss (active leveledUp loss hasUpgrade : Bool)
    (hloss : loss = true) (hup : hasUpgrade = true) :
    step active leveledUp loss hasUpgrade = true := by
  subst hloss; subst hup; cases active <;> cases leveledUp <;> rfl

/-- **CLEAR IFF NO UPGRADE.** With no craftable upgrade remaining, the latch is
forced OFF this cycle — even if it was triggered. The clear dominates. -/
theorem clear_iff_no_upgrade (active leveledUp loss : Bool) :
    step active leveledUp loss false = false := by
  cases active <;> cases leveledUp <;> cases loss <;> rfl

/-- **MONOTONE UNTIL CLEAR.** Once set (`active = true`), with no new level-up or
loss but an upgrade still available, the latch STAYS set — it does not flicker
off while there is still gear to chase. -/
theorem monotone_until_clear (active leveledUp loss hasUpgrade : Bool)
    (hactive : active = true) (hnolvl : leveledUp = false) (hnoloss : loss = false)
    (hup : hasUpgrade = true) :
    step active leveledUp loss hasUpgrade = true := by
  subst hactive; subst hnolvl; subst hnoloss; subst hup; rfl

/-! ### Non-vacuity / corner witnesses. -/

/-- Idle with nothing to do: not active, no trigger ⇒ stays off. -/
example : step false false false true = false := by decide

/-- Held: active, no new trigger, upgrade still available ⇒ stays on
(the monotone case as a closed computation). -/
example : step true false false true = true := by decide

/-- Triggered but already complete: level-up fires yet no upgrade remains ⇒
clears immediately. -/
example : step false true false false = false := by decide

/-- The intermediate `t` is exactly the disjunction; clearing only applies when
`t` was set. With `t = false` and no upgrade, result is still false (vacuously
not "cleared from on"). -/
example : step false false false false = false := by decide

end Formal.GearLatch
