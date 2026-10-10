-- @concept: consumables, fleet, supply @property: safety, monotonicity, totality
/-
The fleet's consumable floor, rebuilt on the chosen loadouts
(`docs/PLAN_consumable_utility.md` increment 4,
`src/artifactsmmo_cli/ai/consumable_floor_core.py`).

USER (2026-10-09), "From the chosen loadouts": for every consumable type some
character's chosen loadout uses, the fleet's minimum BANKED quantity is Σ over
those characters of (units used per fight × `REFILL_HORIZON_FIGHTS`).

USER (2026-10-09), floor shares, "Need ledger + API order": each character
publishes its per-type need; the banked stock is assigned in the account's
`GET /my/characters` order; each character publishes
`need − min(need, max(0, bank − needs ahead of it))`.

## The model

Per consumable type. `share ahead need bank` is one character's share, where
`ahead` is the summed need of the characters before it in the fleet order.
Nat subtraction truncates, so `bank - ahead` is `max(0, bank − ahead)` and the
outer subtraction is never negative.

`fleetShares bank needs` is every character's share, the needs listed in the
fleet order; `fleetShares_getD` says its `i`-th entry is exactly the share the
`i`-th character computes from the needs ahead of it.
-/

namespace Formal.ConsumableFloor

/-- One character's share of the shortfall: its need, less the bank units left
after every character ahead of it took its own need. -/
def share (ahead need bank : Nat) : Nat := need - min need (bank - ahead)

/-- The shares of `needs` (in fleet order), the characters ahead of the first
having summed need `prefix`. -/
def sharesAux (bank : Nat) : Nat → List Nat → List Nat
  | _, [] => []
  | p, n :: ns => share p n bank :: sharesAux bank (p + n) ns

/-- Every character's share, the needs in fleet order. -/
def fleetShares (bank : Nat) (needs : List Nat) : List Nat := sharesAux bank 0 needs

/-! ## Theorems -/

/-- No share exceeds its character's need (and, in `Nat`, none is negative). -/
theorem share_le (ahead need bank : Nat) : share ahead need bank ≤ need := by
  unfold share; omega

/-- MONOTONE: more banked stock never raises a share. -/
theorem share_antitone_bank (ahead need b b' : Nat) (h : b ≤ b') :
    share ahead need b' ≤ share ahead need b := by
  unfold share; omega

/-- With nothing banked every character publishes its whole need. -/
theorem share_zero_bank (ahead need : Nat) : share ahead need 0 = need := by
  unfold share; omega

/-- A lone character (nothing ahead) publishes its need less the bank. -/
theorem share_alone (need bank : Nat) : share 0 need bank = need - bank := by
  unfold share; omega

theorem sharesAux_sum (bank : Nat) :
    ∀ (ns : List Nat) (p : Nat), (sharesAux bank p ns).sum = ns.sum - (bank - p) := by
  intro ns
  induction ns with
  | nil => intro p; simp [sharesAux]
  | cons n ns ih =>
    intro p
    simp only [sharesAux, List.sum_cons, ih (p + n), share]
    omega

/-- THE FLEET SUM: the shares sum exactly to the fleet's shortfall,
`max(0, Σ needs − bank)` — no unit is asked for twice and none is missed. -/
theorem fleetShares_sum (bank : Nat) (needs : List Nat) :
    (fleetShares bank needs).sum = needs.sum - bank := by
  unfold fleetShares
  rw [sharesAux_sum]
  omega

theorem sharesAux_length (bank : Nat) :
    ∀ (ns : List Nat) (p : Nat), (sharesAux bank p ns).length = ns.length := by
  intro ns
  induction ns with
  | nil => intro p; rfl
  | cons n ns ih => intro p; simp [sharesAux, ih]

theorem sharesAux_getD (bank : Nat) :
    ∀ (ns : List Nat) (p i : Nat), i < ns.length →
      (sharesAux bank p ns).getD i 0 = share (p + (ns.take i).sum) (ns.getD i 0) bank := by
  intro ns
  induction ns with
  | nil => intro p i h; simp at h
  | cons n ns ih =>
    intro p i h
    cases i with
    | zero => simp [sharesAux]
    | succ k =>
      simp only [sharesAux, List.getD_cons_succ, List.take_succ_cons, List.sum_cons]
      rw [ih (p + n) k (by simp at h; omega), Nat.add_assoc]

/-- The fleet's shares are the per-character shares: the `i`-th entry is what
the `i`-th character computes from the needs ahead of it. -/
theorem fleetShares_getD (bank : Nat) (needs : List Nat) (i : Nat) (h : i < needs.length) :
    (fleetShares bank needs).getD i 0 = share (needs.take i).sum (needs.getD i 0) bank := by
  unfold fleetShares
  rw [sharesAux_getD bank needs 0 i h, Nat.zero_add]

theorem fleetShares_length (bank : Nat) (needs : List Nat) :
    (fleetShares bank needs).length = needs.length :=
  sharesAux_length bank needs 0

/-! ## Witnesses -/

example : fleetShares 25 [20, 20, 20] = [0, 15, 20] := by decide
example : fleetShares 0 [5, 0, 7] = [5, 0, 7] := by decide
example : fleetShares 100 [20, 20] = [0, 0] := by decide
example : share 20 20 25 = 15 := by decide

end Formal.ConsumableFloor
