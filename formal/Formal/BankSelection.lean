-- @concept: bank, items, crafting @property: safety
/-
Formal model of `select_bank_deposits` (and `hard_critical_codes`,
`_last_resort_deposit`, `kit_selection.best_fighting_weapon` /
`best_gathering_tools`) from `src/artifactsmmo_cli/ai/bank_selection.py`.

## The policy — QUANTITIES, not a keep-SET

`select_bank_deposits(state, game_data, ctx)` deposits, for every held code, the
copies that exceed its BAG keep cap:

    deposit qty = bankable(code) = max 0 (bag[code] - keep_in_bag(code))

sorted by `(-sell_value, code)`.

This REPLACES the old keep-SET policy (`_keep_codes : set[str]`, deleted). A
code-set can only express "keep ALL copies", and that type-level defect WAS the
hoard bug: the best woodcutting tool was in the set, so all EIGHTEEN `copper_axe`
were shielded and DepositAll banked none of them while the weaponcrafting grind
manufactured more. The theorems below are therefore no longer about set
membership (`deposits ∩ keep = ∅`) but about COPIES: what leaves the bag is
exactly the surplus, and what stays is exactly the cap.

## `keepInBag` is OPAQUE here — deliberately

The keep quantity is `inventory_keep.keep_in_bag`, whose combinator (the MAX over
the `KeepReason` registry) is proved in `Formal.InventoryKeep` and whose
individual reasons (a greedy aggregate heal fill, a fuel-bounded recipe-chain
walk, ...) are game-data searches with no scalar to mirror. It enters this model
as an opaque `keepInBag : Nat → Nat` field — exactly the discipline
`Formal.InventoryKeep` uses for its contributions — and is pinned to the REAL
Python end-to-end by `formal/diff/test_bank_selection_diff.py`, which calls the
production `inventory_keep.keep_in_bag` for every code and feeds the resulting
vector to the oracle. What is proved HERE is the deposit selector built on top of
it: the surplus arithmetic, the freeze, the sort, and the last-resort branch.

The transitive task-input protection the deleted `_recipe_materials` walk used to
provide is NOT lost: it is the `COMMITTED_RECIPE` reason of the keep authority
(`inventory_caps._task_chain_demand_pure`, modelled in `Formal.InventoryCaps` /
`Formal.InventoryChainSafe`), and it is now a task-quantity-SCALED demand rather
than a blanket over the closure. `kept_code_not_deposited` below is the general
form of `task_material_not_deposited`: whatever the authority demands to the full
held amount is never deposited, whichever reason demanded it.

## Model

Items are `Nat` codes. Each inventory item carries `(code, qty)`. Weapon
attributes are abstracted to `attack : Nat → Int`, `isWeapon`, `isTool` (has
skill_effects), `hpRestore`. Sell value is `sellValue : Nat → Int`.

Lean core only — no mathlib.

## LAST-RESORT relief (modelled 2026-06-19, slot-aware 2026-07-09)

When the bag can admit NO further item — the quantity cap is hit
(`inventory_free == 0`) OR every slot is occupied (`inventory_slots_free == 0`) —
AND nothing is bankable (every held code sits at or below its keep cap), one
least-critical stack is banked anyway to free a slot; otherwise `FightAction`
(which needs a free slot) cannot fire and leveling stalls. The pick is ordered by
`hard_critical_codes` (`inKeepBase` here: coin / task item / HP consumable / best
weapon / working tool), then sell value, then code. Banking is recoverable, so
this loses nothing. `selectBankDeposits` IS the full production function.
-/

namespace Formal.BankSelection

/-! ### State abstraction. -/

/-- The inputs `select_bank_deposits` reads, abstracted to integer/Nat data.
* `tasksCoin`  — the `TASKS_COIN` code (the `CURRENCY` / `KEEP_ALL` code);
* `taskCode`   — `some c` if the character has an active task, else `none`;
* `inventory`  — `(code, qty)` association list (Python `state.inventory.items()`);
* `equipped`   — equipped item codes (`state.equipment` values, non-None);
* `attack`     — Σ element attack for a weapon item;
* `isWeapon`   — `stats.type_ = "weapon"`;
* `isTool`     — `stats.skill_effects` nonempty (a gathering tool);
* `hpRestore`  — `stats.hp_restore`;
* `sellValue`  — max NPC buy price (0 if none);
* `keepInBag`  — `inventory_keep.keep_in_bag(code, ...)`: the copies that must
  STAY in the bag. Opaque (see the header): proved in `Formal.InventoryKeep`,
  pinned to the real Python by the differential. -/
structure State where
  tasksCoin : Nat
  taskCode : Option Nat
  inventory : List (Nat × Nat)
  /-- `state.inventory_max` — total item capacity. With `inventoryUsed` (Σ qty) this
      gives `inventoryFree`, which the LAST-RESORT relief branch reads (`== 0`). -/
  inventoryMax : Nat
  /-- `state.inventory_slots_max` — the number of inventory SLOTS (distinct-stack
      cap). With `inventorySlotsUsed` (count of positive stacks) this gives
      `inventorySlotsFree`, the OTHER exhaustion the last-resort branch reads
      (`== 0`): many low-count kept stacks fill all slots before the quantity cap. -/
  inventorySlotsMax : Nat
  equipped : List Nat
  attack : Nat → Int
  isWeapon : Nat → Bool
  isTool : Nat → Bool
  hpRestore : Nat → Int
  sellValue : Nat → Int
  keepInBag : Nat → Nat

/-! ### Best fighting weapon (argmax over inventory ∪ equipped).

`kit_selection.best_fighting_weapon`. It identifies the ONE code the character
fights with; the keep authority's `COMBAT_WEAPON` reason turns that into the
quantity 1. (Conflating the two — "this is the weapon" with "keep every copy of
it" — is the bug class this file's header describes.) -/

/-- Weapon candidates: inventory codes ∪ equipped codes (deduplicated). Mirrors
`set(state.inventory)`+`equipment.values()`; dedup keeps the fold deterministic. -/
def weaponCandidates (s : State) : List Nat :=
  (s.inventory.map Prod.fst ++ s.equipped).eraseDups

/-- A code is a fighting-weapon candidate: a `weapon` that is NOT a tool. Mirrors
`stats.type_ == "weapon" and not stats.skill_effects`. -/
def isFightingWeapon (s : State) (code : Nat) : Bool :=
  s.isWeapon code && !s.isTool code

/-- Fold step for the best fighting weapon. Carries the running best
`(attack, code)`. A candidate replaces the best iff it is a fighting weapon AND
(`best = none` ∨ strictly higher attack ∨ equal attack with strictly smaller
code). This mirrors the Python `if best is None or attack > best[0] or (attack ==
best[0] and code < best[1])`. -/
def betterWeapon (s : State) (best : Option (Int × Nat)) (code : Nat) :
    Option (Int × Nat) :=
  if isFightingWeapon s code then
    match best with
    | none => some (s.attack code, code)
    | some (batk, bcode) =>
      if s.attack code > batk || (s.attack code == batk && code < bcode)
      then some (s.attack code, code)
      else some (batk, bcode)
  else best

/-- The best-weapon fold: left fold over the candidates carrying the running best
`(attack, code)`. The candidate list is fixed by `weaponCandidates`. -/
def bestWeaponFold (s : State) : Option (Int × Nat) :=
  (weaponCandidates s).foldl (betterWeapon s) none

/-- The best fighting weapon code. -/
def bestWeaponCode (s : State) : Option Nat :=
  match bestWeaponFold s with
  | none => none
  | some (_, code) => some code

/-! ### Best gathering tool (`kit_selection.best_gathering_tools`).

Python keeps, per gathering skill, the argmax of `abs(gather_score)` over
inventory ∪ equipped, ties broken by code ascending. In THIS model's input
abstraction toolness is a single boolean (the differential fixture maps every tool
to one skill at unit magnitude), so the per-skill argmax reduces exactly to the
LOWEST tool code. -/

/-- Fold step for the best gathering tool: first/lowest tool code wins. -/
def betterTool (s : State) (best : Option Nat) (code : Nat) : Option Nat :=
  if s.isTool code then
    match best with
    | none => some code
    | some bcode => if code < bcode then some code else some bcode
  else best

/-- Tool candidates: inventory codes with qty > 0 ∪ equipped. Python's
`best_gathering_tools` filters `q > 0` — a zero-qty stack is not an owned
tool (unlike `weaponCandidates`, whose Python twin iterates codes only). -/
def toolCandidates (s : State) : List Nat :=
  ((s.inventory.filter (fun cq => cq.2 > 0)).map Prod.fst ++ s.equipped).eraseDups

/-- The working gathering-tool code (lowest owned tool), if any tool is owned. -/
def bestToolCode (s : State) : Option Nat :=
  (toolCandidates s).foldl (betterTool s) none

/-! ### Hard-critical codes (`bank_selection.hard_critical_codes`).

A criticality RANKING for the last-resort pick — NOT a keep-set (nothing in this
file protects a code; only `keepInBag` protects, and it protects COPIES). -/

/-- A code is HP-restoring AND in the inventory (Python iterates `state.inventory`
adding codes with `hp_restore > 0`). -/
def isKeptHp (s : State) (code : Nat) : Bool :=
  decide (code ∈ s.inventory.map Prod.fst) && decide (s.hpRestore code > 0)

/-- `hard_critical_codes`: the codes the last-resort sheds LAST —
* `code = tasksCoin`, or
* `some code = taskCode`, or
* an HP-restore item in the inventory, or
* the best fighting weapon, or
* the working gathering tool. -/
def inKeepBase (s : State) (code : Nat) : Bool :=
  decide (code = s.tasksCoin)
  || decide (s.taskCode = some code)
  || isKeptHp s code
  || decide (bestWeaponCode s = some code)
  || decide (bestToolCode s = some code)

/-! ### The deposit list — the surplus above `keepInBag`. -/

/-- `inventory_keep.bankable` at one inventory entry: the copies above the bag
cap. Nat subtraction saturates, which IS the Python `max(0, ...)` — so a cap that
EXCEEDS the held amount (two committed roots whose combined demand does not fit,
or the `KEEP_ALL` currency sentinel) yields 0, never a negative deposit. -/
def bankableQty (s : State) (cq : Nat × Nat) : Nat := cq.2 - s.keepInBag cq.1

/-- An entry contributes a deposit iff it is held (`qty > 0`) and has surplus. -/
def isBankable (s : State) (cq : Nat × Nat) : Bool :=
  decide (cq.2 > 0) && decide (bankableQty s cq > 0)

/-- The deposit candidates: one `(code, surplus)` per held code with surplus,
BEFORE sorting. -/
def depositCandidates (s : State) : List (Nat × Nat) :=
  (s.inventory.filter (isBankable s)).map (fun cq => (cq.1, bankableQty s cq))

/-- Sort key comparison: `(-sellValue, code)` ascending = sellValue descending,
then code ascending. -/
def depositLe (s : State) (cq₁ cq₂ : Nat × Nat) : Bool :=
  let v1 := s.sellValue cq₁.1
  let v2 := s.sellValue cq₂.1
  decide (v1 > v2) || (decide (v1 = v2) && decide (cq₁.1 ≤ cq₂.1))

/-- The deposit list, sorted by `(-sellValue, code)`. -/
def deposits (s : State) : List (Nat × Nat) :=
  (depositCandidates s).mergeSort (fun a b => depositLe s a b)

/-! ### Theorems: the deposit is EXACTLY the surplus. -/

/-- `deposits_exact`: the deposit CANDIDATES are EXACTLY one entry per held code
whose held amount EXCEEDS its bag cap, carrying the excess. (The sort is a
permutation; `deposits_perm` relates the sorted list to the candidates.) -/
theorem deposits_exact (s : State) (cq : Nat × Nat) :
    cq ∈ depositCandidates s
      ↔ ∃ held, (cq.1, held) ∈ s.inventory ∧ held > 0
          ∧ held > s.keepInBag cq.1 ∧ cq.2 = held - s.keepInBag cq.1 := by
  unfold depositCandidates
  rw [List.mem_map]
  constructor
  · rintro ⟨⟨ac, aq⟩, hmem, heq⟩
    rw [List.mem_filter] at hmem
    obtain ⟨hinv, hcond⟩ := hmem
    unfold isBankable bankableQty at hcond
    rw [Bool.and_eq_true] at hcond
    obtain ⟨hq, hs⟩ := hcond
    simp only [decide_eq_true_eq] at hq hs
    subst heq
    exact ⟨aq, hinv, hq, by simpa using (by omega : s.keepInBag ac < aq), rfl⟩
  · rintro ⟨held, hinv, hq, hgt, hval⟩
    refine ⟨(cq.1, held), ?_, ?_⟩
    · rw [List.mem_filter]
      refine ⟨hinv, ?_⟩
      unfold isBankable bankableQty
      simp only [Bool.and_eq_true, decide_eq_true_eq]
      exact ⟨hq, by omega⟩
    · unfold bankableQty
      simp only
      rw [← hval]

/-- The sorted deposit list is a PERMUTATION of the candidates (same entries,
different order). -/
theorem deposits_perm (s : State) :
    (deposits s).Perm (depositCandidates s) :=
  List.mergeSort_perm _ _

/-- `deposits` membership = candidate membership (via the permutation). -/
theorem deposits_mem_iff (s : State) (cq : Nat × Nat) :
    cq ∈ deposits s
      ↔ ∃ held, (cq.1, held) ∈ s.inventory ∧ held > 0
          ∧ held > s.keepInBag cq.1 ∧ cq.2 = held - s.keepInBag cq.1 := by
  rw [← deposits_exact]
  exact (deposits_perm s).mem_iff

/-- **THE safety theorem** (the freeze invariant, re-cast onto copies): banking a
deposited quantity leaves EXACTLY the keep cap in the bag. Nothing the keep
authority demands ever leaves — and nothing above it ever stays. This is strictly
stronger than the old set-level `deposits ∩ keep = ∅`, which could only say that a
protected CODE was untouched (and therefore hoarded every copy of it). -/
theorem deposit_leaves_keep (s : State) (cq : Nat × Nat) (h : cq ∈ deposits s) :
    ∃ held, (cq.1, held) ∈ s.inventory ∧ held - cq.2 = s.keepInBag cq.1 := by
  obtain ⟨held, hinv, _, hgt, hval⟩ := (deposits_mem_iff s cq).mp h
  exact ⟨held, hinv, by omega⟩

/-- Every deposited entry came from the inventory and has positive quantity. -/
theorem deposits_from_inventory (s : State) (cq : Nat × Nat) (h : cq ∈ deposits s) :
    (∃ held, (cq.1, held) ∈ s.inventory ∧ held > 0) ∧ cq.2 > 0 := by
  obtain ⟨held, hinv, hq, hgt, hval⟩ := (deposits_mem_iff s cq).mp h
  exact ⟨⟨held, hinv, hq⟩, by omega⟩

/-- **`kept_code_not_deposited`**: a code the authority demands to (at least) the
full held amount is NEVER deposited, in ANY quantity.

This is the general form of the old `task_material_not_deposited`. Instantiate it
with `COMMITTED_RECIPE` and it says the active task's own recipe inputs are never
banked (the PursueTask freeze guarantee); with `CURRENCY` (`KEEP_ALL`) it says the
task coins never are; with `WORKING_KIT` at held ≤ 1 it says the last working axe
never is — while the 17 spares, whose held EXCEEDS the cap, do bank. -/
theorem kept_code_not_deposited (s : State) (c : Nat)
    (h : ∀ held, (c, held) ∈ s.inventory → held ≤ s.keepInBag c) :
    ∀ q, (c, q) ∉ deposits s := by
  intro q hmem
  obtain ⟨held, hinv, _, hgt, _⟩ := (deposits_mem_iff s (c, q)).mp hmem
  exact absurd (h held hinv) (by simpa using Nat.not_le.mpr hgt)

/-- The `KEEP_ALL` currency escape hatch at the deposit boundary: with the coin's
cap at the sentinel, no holdable quantity of `tasks_coin` is ever banked. (The
sentinel exceeds any bag the server can hand out, which is the second hypothesis —
stated, not assumed away.) -/
theorem currency_never_deposited (s : State)
    (hcap : s.keepInBag s.tasksCoin = 1000000)
    (hbag : ∀ held, (s.tasksCoin, held) ∈ s.inventory → held ≤ 1000000) :
    ∀ q, (s.tasksCoin, q) ∉ deposits s :=
  kept_code_not_deposited s s.tasksCoin (fun held hmem => by
    rw [hcap]; exact hbag held hmem)

/-! ### Non-vacuity: the axe row.

Every hypothesis above is satisfiable, and the headline bug is refuted on the
exact numbers of the live incident: 18 `copper_axe` held, `WORKING_KIT` demands 1,
so 17 are selected for deposit and 1 stays. Under the deleted code-set the axe was
simply "kept" and 0 were selected. -/

/-- The surplus arithmetic on the live row. -/
theorem copper_axe_surplus (s : State) (c : Nat) (hkeep : s.keepInBag c = 1) :
    bankableQty s (c, 18) = 17 := by
  unfold bankableQty
  simp [hkeep]

/-- ...and the row really IS selected: `(axe, 17)` is a deposit candidate, so
`deposits_exact`'s hypothesis is satisfiable (the theorem is not vacuous) and the
17 spares leave the bag. -/
theorem copper_axe_hoard_refuted (s : State) (c : Nat)
    (hkeep : s.keepInBag c = 1) (hmem : (c, 18) ∈ s.inventory) :
    (c, 17) ∈ depositCandidates s := by
  rw [deposits_exact]
  refine ⟨18, hmem, by omega, ?_, ?_⟩ <;> simp [hkeep]

/-- ...while the ONE working copy is untouchable: at 1 held (cap 1) nothing of the
code is deposited. Both halves hold of the SAME code — that is what a quantity can
express and a code-set cannot. -/
theorem copper_axe_working_copy_kept (s : State) (c : Nat)
    (hkeep : s.keepInBag c = 1)
    (hinv : ∀ held, (c, held) ∈ s.inventory → held ≤ 1) :
    ∀ q, (c, q) ∉ deposits s :=
  kept_code_not_deposited s c (fun held hmem => by rw [hkeep]; exact hinv held hmem)

/-! ### Capacity + the LAST-RESORT relief (production parity, 2026-06-19;
slot-aware 2026-07-09). -/

/-- `state.inventory_used` — Σ stack quantities. -/
def inventoryUsed (s : State) : Nat := (s.inventory.map Prod.snd).sum

/-- `state.inventory_free` — `inventory_max − inventory_used` (Nat sub saturates). -/
def inventoryFree (s : State) : Nat := s.inventoryMax - inventoryUsed s

/-- `state.inventory_slots_used` — the number of occupied SLOTS = count of DISTINCT
inventory codes holding a POSITIVE quantity. Mirrors the Python property
`sum(1 for q in inventory.values() if q > 0)` exactly. -/
def inventorySlotsUsed (s : State) : Nat :=
  ((s.inventory.filter (fun cq => decide (cq.2 > 0))).map Prod.fst).eraseDups.length

/-- `state.inventory_slots_free` — `inventory_slots_max − inventory_slots_used`
(Nat sub saturates). The last-resort branch reads `== 0`: all slots occupied is the
real "cannot admit another item" stall even when quantity capacity remains. -/
def inventorySlotsFree (s : State) : Nat := s.inventorySlotsMax - inventorySlotsUsed s

/-- Last-resort sort comparator: `(inKeepBase, sellValue, code)` ascending. Mirrors
`_last_resort_deposit`'s key (the `ctx.step_profile` term is modelled empty — the
differential drives `select_bank_deposits` with the default no-profile context). -/
def lastResortLe (s : State) (cq₁ cq₂ : Nat × Nat) : Bool :=
  let c1 := inKeepBase s cq₁.1
  let c2 := inKeepBase s cq₂.1
  let v1 := s.sellValue cq₁.1
  let v2 := s.sellValue cq₂.1
  (!c1 && c2)
  || (c1 == c2 && (decide (v1 < v2) || (decide (v1 = v2) && decide (cq₁.1 ≤ cq₂.1))))

/-- Last-resort candidates: inventory entries with `qty > 0` (in this branch every
held code is at or below its cap, so criticality only ORDERS the pick). -/
def lastResortCandidates (s : State) : List (Nat × Nat) :=
  s.inventory.filter (fun cq => decide (cq.2 > 0))

/-- The single least-critical stack to bank when the bag is full and nothing is
bankable; `none` only when the bag is empty. Mirrors `_last_resort_deposit`. -/
def lastResortDeposit (s : State) : Option (Nat × Nat) :=
  match (lastResortCandidates s).mergeSort (fun a b => lastResortLe s a b) with
  | [] => none
  | x :: _ => some x

/-- **`select_bank_deposits` IN FULL** (the production function): the surplus
deposits when non-empty, else — only when the bag can admit no further item — the
single last-resort stack, else `[]`. -/
def selectBankDeposits (s : State) : List (Nat × Nat) :=
  if deposits s ≠ [] then deposits s
  else if inventoryFree s = 0 ∨ inventorySlotsFree s = 0 then
    match lastResortDeposit s with
    | some item => [item]
    | none => []
  else []

/-! ### selectBankDeposits theorems — normal-path parity + the relaxed freeze. -/

/-- On the NORMAL path (BOTH quantity room AND slot room), `selectBankDeposits =
deposits`: the last-resort never fires while the bag can still admit an item, so
every `deposits` theorem (incl. `deposit_leaves_keep`) transfers verbatim. -/
theorem selectBankDeposits_eq_deposits_of_free_pos (s : State)
    (hfree : inventoryFree s > 0) (hslots : inventorySlotsFree s > 0) :
    selectBankDeposits s = deposits s := by
  unfold selectBankDeposits
  by_cases hd : deposits s = []
  · rw [if_neg (by simp [hd])]
    have hfull : ¬ (inventoryFree s = 0 ∨ inventorySlotsFree s = 0) := by
      rintro (h | h) <;> omega
    rw [if_neg hfull, hd]
  · rw [if_pos hd]

/-- **Relaxed freeze invariant** — the honest statement of the guarantee: while the
bag can still admit another item, every deposit leaves EXACTLY the keep cap behind.
When either capacity is exhausted the last-resort deliberately banks ONE protected
stack (recoverable), so the freeze CANNOT hold there — and must not, or the bag
stalls and the bot stops fighting. -/
theorem keep_respected_of_free_pos (s : State) (cq : Nat × Nat)
    (hfree : inventoryFree s > 0) (hslots : inventorySlotsFree s > 0)
    (h : cq ∈ selectBankDeposits s) :
    ∃ held, (cq.1, held) ∈ s.inventory ∧ held - cq.2 = s.keepInBag cq.1 := by
  rw [selectBankDeposits_eq_deposits_of_free_pos s hfree hslots] at h
  exact deposit_leaves_keep s cq h

/-- The last-resort pick is a real inventory entry with positive quantity — so
banking it FREES a slot (the production guarantee that breaks the livelock). -/
theorem lastResortDeposit_mem (s : State) (cq : Nat × Nat)
    (h : lastResortDeposit s = some cq) : cq ∈ s.inventory ∧ cq.2 > 0 := by
  unfold lastResortDeposit at h
  split at h
  · exact absurd h (by simp)
  · rename_i x xs heq
    simp only [Option.some.injEq] at h
    have hmem : cq ∈ (lastResortCandidates s).mergeSort (fun a b => lastResortLe s a b) := by
      rw [heq, ← h]; simp
    have hperm := List.mergeSort_perm (lastResortCandidates s) (fun a b => lastResortLe s a b)
    have hcand : cq ∈ lastResortCandidates s := hperm.mem_iff.mp hmem
    unfold lastResortCandidates at hcand
    rw [List.mem_filter] at hcand
    exact ⟨hcand.1, by simpa using hcand.2⟩

/-- **Last-resort relief frees a slot.** When the bag can admit no more items —
EITHER quantity-full OR slots-full — and nothing is bankable, `selectBankDeposits`
banks exactly one inventory stack, so a slot frees and the fight can fire. -/
theorem selectBankDeposits_frees_slot_when_full (s : State)
    (hd : deposits s = [])
    (hfull : inventoryFree s = 0 ∨ inventorySlotsFree s = 0)
    (cq : Nat × Nat) (hlr : lastResortDeposit s = some cq) :
    selectBankDeposits s = [cq] ∧ cq ∈ s.inventory ∧ cq.2 > 0 := by
  refine ⟨?_, lastResortDeposit_mem s cq hlr⟩
  unfold selectBankDeposits
  rw [if_neg (by simp [hd]), if_pos hfull, hlr]

/-! ### best_weapon_argmax: the best fighting weapon is the max-attack non-tool
weapon over inventory ∪ equipped, ties broken by code ascending. -/

/-- The running best after a fold prefix is always a fighting weapon (or none). -/
theorem bestWeaponFold_isFighting (s : State) :
    ∀ (l : List Nat) (acc : Option (Int × Nat)),
      (∀ p, acc = some p → isFightingWeapon s p.2 = true) →
      (∀ p, l.foldl (betterWeapon s) acc = some p → isFightingWeapon s p.2 = true) := by
  intro l
  induction l with
  | nil => intro acc hacc p hp; exact hacc p hp
  | cons x xs ih =>
    intro acc hacc p hp
    simp only [List.foldl_cons] at hp
    apply ih (betterWeapon s acc x) _ p hp
    intro q hq
    unfold betterWeapon at hq
    by_cases hf : isFightingWeapon s x = true
    · rw [if_pos hf] at hq
      cases acc with
      | none =>
        simp only [Option.some.injEq] at hq
        rw [← hq]; exact hf
      | some bp =>
        obtain ⟨batk, bcode⟩ := bp
        simp only at hq
        by_cases hcmp : (decide (s.attack x > batk) || (s.attack x == batk && decide (x < bcode))) = true
        · rw [if_pos hcmp, Option.some.injEq] at hq
          rw [← hq]; exact hf
        · rw [if_neg hcmp] at hq
          exact hacc q hq
    · rw [if_neg hf] at hq
      exact hacc q hq

/-- `best_weapon_is_fighting`: the chosen best weapon is a fighting weapon (a
`weapon` that is not a tool) — tools are excluded. -/
theorem best_weapon_is_fighting (s : State) (c : Nat) (h : bestWeaponCode s = some c) :
    isFightingWeapon s c = true := by
  unfold bestWeaponCode at h
  cases hf : bestWeaponFold s with
  | none => rw [hf] at h; simp at h
  | some p =>
    rw [hf] at h
    simp only [Option.some.injEq] at h
    have hfight : isFightingWeapon s p.2 = true := by
      apply bestWeaponFold_isFighting s (weaponCandidates s) none (by simp) p
      exact hf
    rw [← h]; exact hfight

/-- The fold result's attack dominates the running accumulator's attack and every
fighting-weapon candidate's attack in the prefix processed. The argmax is the
MAXIMUM attack over fighting weapons. -/
theorem bestWeaponFold_ge (s : State) :
    ∀ (l : List Nat) (acc : Option (Int × Nat)),
      (∃ q, l.foldl (betterWeapon s) acc = some q ∧
        (∀ ap, acc = some ap → ap.1 ≤ q.1) ∧
        (∀ y ∈ l, isFightingWeapon s y = true → s.attack y ≤ q.1))
      ∨ (l.foldl (betterWeapon s) acc = none) := by
  intro l
  induction l with
  | nil =>
    intro acc
    cases acc with
    | none => exact Or.inr rfl
    | some ap =>
      refine Or.inl ⟨ap, rfl, ?_, ?_⟩
      · intro ap' h; rw [Option.some.injEq] at h; rw [h]; exact Int.le_refl _
      · intro y hy; exact absurd hy (List.not_mem_nil)
  | cons x xs ih =>
    intro acc
    simp only [List.foldl_cons]
    rcases ih (betterWeapon s acc x) with ⟨q, hfold, hacc', hcands'⟩ | hnone
    · refine Or.inl ⟨q, hfold, ?_, ?_⟩
      · intro ap hap
        have hkey : ∀ ap', acc = some ap' →
            ∃ bp, betterWeapon s acc x = some bp ∧ ap'.1 ≤ bp.1 := by
          intro ap' hap'
          by_cases hf : isFightingWeapon s x = true
          · obtain ⟨batk, bcode⟩ := ap'
            by_cases hcmp : (decide (s.attack x > batk)
                || (s.attack x == batk && decide (x < bcode))) = true
            · refine ⟨(s.attack x, x), ?_, ?_⟩
              · simp only [betterWeapon, hf, hap', if_true]; rw [if_pos hcmp]
              · simp only [Bool.or_eq_true, decide_eq_true_eq, beq_iff_eq, Bool.and_eq_true] at hcmp
                rcases hcmp with h1 | ⟨h2, _⟩
                · exact Int.le_of_lt h1
                · exact Int.le_of_eq h2.symm
            · refine ⟨(batk, bcode), ?_, Int.le_refl _⟩
              simp only [betterWeapon, hf, hap', if_true]; rw [if_neg hcmp]
          · refine ⟨ap', ?_, Int.le_refl _⟩
            rw [hap']; unfold betterWeapon; rw [if_neg hf]
        obtain ⟨bp, hbp, hle⟩ := hkey ap hap
        exact Int.le_trans hle (hacc' bp hbp)
      · intro y hy hfy
        rcases List.mem_cons.mp hy with hyx | hyxs
        · subst hyx
          have hkey : ∃ bp, betterWeapon s acc y = some bp ∧ s.attack y ≤ bp.1 := by
            cases acc with
            | none => exact ⟨(s.attack y, y), by simp only [betterWeapon, hfy, if_true], Int.le_refl _⟩
            | some ap =>
              obtain ⟨batk, bcode⟩ := ap
              by_cases hcmp : (decide (s.attack y > batk)
                  || (s.attack y == batk && decide (y < bcode))) = true
              · refine ⟨(s.attack y, y), ?_, Int.le_refl _⟩
                simp only [betterWeapon, hfy, if_true]; rw [if_pos hcmp]
              · refine ⟨(batk, bcode), ?_, ?_⟩
                · simp only [betterWeapon, hfy, if_true]; rw [if_neg hcmp]
                · simp only [Bool.or_eq_true, decide_eq_true_eq, beq_iff_eq, Bool.and_eq_true,
                    not_or, not_and, Int.not_lt] at hcmp
                  exact hcmp.1
          obtain ⟨bp, hbp, hle⟩ := hkey
          exact Int.le_trans hle (hacc' bp hbp)
        · exact hcands' y hyxs hfy
    · exact Or.inr hnone

/-- The recorded attack in the fold equals `s.attack` of the recorded code. -/
theorem bestWeaponFold_attack_eq (s : State) :
    ∀ (l : List Nat) (acc : Option (Int × Nat)) (q : Int × Nat),
      l.foldl (betterWeapon s) acc = some q →
      (∀ ap, acc = some ap → ap.1 = s.attack ap.2) →
      q.1 = s.attack q.2 := by
  intro l
  induction l with
  | nil =>
    intro acc q hfold hinv
    simp only [List.foldl_nil] at hfold
    exact hinv q hfold
  | cons x xs ih =>
    intro acc q hfold hinv
    simp only [List.foldl_cons] at hfold
    apply ih (betterWeapon s acc x) q hfold
    intro ap hap
    unfold betterWeapon at hap
    by_cases hf : isFightingWeapon s x = true
    · rw [if_pos hf] at hap
      cases acc with
      | none => simp only [Option.some.injEq] at hap; rw [← hap]
      | some bp =>
        obtain ⟨batk, bcode⟩ := bp
        simp only at hap
        by_cases hcmp : (decide (s.attack x > batk)
            || (s.attack x == batk && decide (x < bcode))) = true
        · rw [if_pos hcmp, Option.some.injEq] at hap; rw [← hap]
        · rw [if_neg hcmp, Option.some.injEq] at hap
          rw [← hap]; exact hinv (batk, bcode) rfl
    · rw [if_neg hf] at hap
      exact hinv ap hap

/-- `best_weapon_argmax`: the best fighting weapon's attack is ≥ every fighting
weapon candidate's attack — the argmax (maximum) over inventory ∪ equipped of the
non-tool weapons. -/
theorem best_weapon_argmax (s : State) (c : Nat) (h : bestWeaponCode s = some c) :
    ∀ y ∈ weaponCandidates s, isFightingWeapon s y = true →
      s.attack y ≤ s.attack c := by
  intro y hy hfy
  rcases bestWeaponFold_ge s (weaponCandidates s) none with ⟨q, hfold, _, hcands⟩ | hnone
  · have hcode : q.2 = c := by
      unfold bestWeaponCode bestWeaponFold at h
      rw [hfold] at h
      simp only [Option.some.injEq] at h
      exact h
    have hcands' := hcands y hy hfy
    have hq2 : q.1 = s.attack q.2 :=
      bestWeaponFold_attack_eq s (weaponCandidates s) none q hfold (by simp)
    rw [hq2, hcode] at hcands'
    exact hcands'
  · unfold bestWeaponCode bestWeaponFold at h
    rw [hnone] at h
    simp at h

end Formal.BankSelection
