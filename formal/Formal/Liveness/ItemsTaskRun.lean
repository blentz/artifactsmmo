-- @concept: tasks @property: safety, totality, reachability

/-! # Items-Task Run — inventory-COUPLED termination model

This module lands the HONEST end-to-end termination story for items-task
pursuit over a **fresh, purpose-built, inventory-coupled** model — NOT a
retrofit of the shared collapsed Liveness `State`.

## Why a new model

The shared Liveness `State` model collapses the `.taskTrade` transition: in
that model `applyActionKind .taskTrade` advances `taskProgress` *without*
consuming any inventory. That decoupling is exactly why an end-to-end
"feasible items-task terminates" capstone over the shared model would be
**vacuous** — progress can advance for free, so a termination proof there
proves nothing about the real game where the API `taskTrade` action *consumes*
the obtained task item.

Reproving the ~100 shared-model modules to thread inventory consumption
through `.taskTrade` was the multi-session blocker. Instead, this module is a
small standalone model where trade GENUINELY consumes the held task item,
faithful to the real game:

* `obtain s k`  — gather/craft deposits `k` task items into inventory
  (`held += k`). Mirrors the gather→craft→deposit chain that produces the
  task item.
* `trade s`     — the API `taskTrade`: it **requires** a held item and
  **consumes** exactly one, advancing progress by one. This is the coupling
  the rejected capstone lacked: `held -= 1` AND `progress += 1`, together,
  atomically, only when `0 < held ∧ progress < total`.

## What is proved (the non-vacuity contract)

* `trade_consumes` — SAFETY/coupling: when fireable, trade advances progress
  by exactly one AND consumes exactly one held item. Progress NEVER advances
  without an inventory decrement.
* `trade_stuck_without_held` — no free progress: with `held = 0` trade is a
  no-op (it cannot manufacture progress out of nothing).
* `run_total` — TOTALITY: `trade` (and the whole `applyRun`) always returns a
  defined `RunState`.
* `obtain_then_trades_reach` — REACHABILITY: from `progress = p < total`,
  `obtain (total - p)` then `replicate (total - p) trade` reaches
  `progress = total`. Well-defined precisely because each trade has `held > 0`
  (the obtain front-loaded exactly enough — the coupling makes the witness
  load-bearing, not free).
* `held_accounts` — THE KEY non-vacuity witness: starting `held = 0`,
  `obtain (total - p)`, then `(total - p)` trades, ends `held = 0` and
  `progress = total`. The whole run consumes EXACTLY `(total - p)` items: no
  free progress, obtain and trade are inventory-coupled.

A concrete `#eval`/`example` witness (`p = 0, total = 3`) closes the file:
`obtain 3` then `trade` thrice → `held = 0, progress = 3`.

Core-only (no Mathlib); `Nat` arithmetic + `omega`/`induction` suffice.
NO `sorry`, NO `native_decide`, NO custom axioms.
-/

namespace Formal.Liveness.ItemsTaskRun

/-- A minimal inventory-coupled run state for items-task pursuit.

* `held`     — units of the task item currently in inventory.
* `progress` — task units already delivered (traded).
* `total`    — task units required for completion.

The invariant the model maintains is purely operational: `trade` is the only
way to advance `progress`, and it can only do so by decrementing `held`. -/
structure RunState where
  held : Nat
  progress : Nat
  total : Nat
  deriving Repr, DecidableEq

/-- `obtain s k` — gather/craft deposits `k` task items into inventory.
    Mirrors the produce-then-deposit chain; it touches ONLY `held`. -/
def obtain (s : RunState) (k : Nat) : RunState :=
  { s with held := s.held + k }

/-- `trade s` — the API `taskTrade`. It REQUIRES a held item and CONSUMES
    exactly one, advancing progress by one, but only while progress is below
    total. Otherwise it is a no-op (defined for all states → totality). -/
def trade (s : RunState) : RunState :=
  if 0 < s.held ∧ s.progress < s.total then
    { s with held := s.held - 1, progress := s.progress + 1 }
  else
    s

/-- `applyRun s plan` — fold a list of run steps over the state. A `plan` is a
    list of `RunState → RunState` steps (the `obtain k` prefix and the `trade`
    tail). Total by construction. -/
def applyRun (s : RunState) (plan : List (RunState → RunState)) : RunState :=
  plan.foldl (fun acc f => f acc) s

/-! ## SAFETY / coupling -/

/-- **SAFETY (coupling)** — when trade is fireable (`0 < held` and
    `progress < total`), it advances progress by exactly one AND consumes
    exactly one held item. Progress advances ONLY by consuming inventory. -/
theorem trade_consumes (s : RunState)
    (h : 0 < s.held ∧ s.progress < s.total) :
    (trade s).held = s.held - 1 ∧ (trade s).progress = s.progress + 1 := by
  unfold trade
  rw [if_pos h]
  exact ⟨rfl, rfl⟩

/-- **SAFETY (no free progress)** — with no held item, trade is a no-op. The
    model cannot manufacture progress out of an empty inventory. -/
theorem trade_stuck_without_held (s : RunState) (h : s.held = 0) :
    trade s = s := by
  unfold trade
  rw [if_neg]
  rintro ⟨hpos, _⟩
  omega

/-- Companion: trade never advances progress past total (no over-trade). -/
theorem trade_stuck_at_total (s : RunState) (h : s.total ≤ s.progress) :
    trade s = s := by
  unfold trade
  rw [if_neg]
  rintro ⟨_, hlt⟩
  omega

/-! ## TOTALITY -/

/-- **TOTALITY** — `trade` is defined on every state (it is a total function;
    the `else` branch makes the no-fire case a defined no-op). Stated as a
    reflexivity witness that `trade s` exists and equals itself. -/
theorem run_total (s : RunState) : ∃ t : RunState, trade s = t :=
  ⟨trade s, rfl⟩

/-- **TOTALITY** — `applyRun` is defined for every plan and state. -/
theorem applyRun_total (s : RunState) (plan : List (RunState → RunState)) :
    ∃ t : RunState, applyRun s plan = t :=
  ⟨applyRun s plan, rfl⟩

/-! ## Fold lemmas for `trade` replication -/

/-- `applyRun s (f :: rest) = applyRun (f s) rest`. -/
theorem applyRun_cons (s : RunState) (f : RunState → RunState)
    (rest : List (RunState → RunState)) :
    applyRun s (f :: rest) = applyRun (f s) rest := by
  unfold applyRun
  rfl

/-- Applying `n` trades when `held` starts at exactly `n` and there is enough
    remaining total: progress climbs by `n`, held drops to `held - n`,
    provided `progress + n ≤ total` so every trade fires. We prove the
    combined accounting directly by induction. -/
theorem replicate_trade_accounts :
    ∀ (n : Nat) (s : RunState),
      s.held = n → s.progress + n ≤ s.total →
        (applyRun s (List.replicate n trade)).progress = s.progress + n
        ∧ (applyRun s (List.replicate n trade)).held = s.held - n
        ∧ (applyRun s (List.replicate n trade)).total = s.total := by
  intro n
  induction n with
  | zero =>
    intro s _ _
    refine ⟨?_, ?_, ?_⟩ <;> simp [applyRun]
  | succ k ih =>
    intro s hHeld hRoom
    -- replicate (k+1) trade = trade :: replicate k trade
    show (applyRun s (trade :: List.replicate k trade)).progress = s.progress + (k + 1)
       ∧ (applyRun s (trade :: List.replicate k trade)).held = s.held - (k + 1)
       ∧ (applyRun s (trade :: List.replicate k trade)).total = s.total
    rw [applyRun_cons]
    -- First trade fires: 0 < held (= k+1) and progress < total.
    have hFire : 0 < s.held ∧ s.progress < s.total := by
      constructor <;> omega
    have hCons := trade_consumes s hFire
    -- total preserved by trade
    have hTot : (trade s).total = s.total := by
      unfold trade; rw [if_pos hFire]
    -- Set up the IH on (trade s).
    have hHeld' : (trade s).held = k := by rw [hCons.1, hHeld]; omega
    have hRoom' : (trade s).progress + k ≤ (trade s).total := by
      rw [hCons.2, hTot]; omega
    obtain ⟨ihP, ihH, ihT⟩ := ih (trade s) hHeld' hRoom'
    rw [hCons.2] at ihP
    rw [hCons.1] at ihH
    rw [hTot] at ihT
    rw [hHeld] at ihH ⊢
    refine ⟨by omega, by omega, ihT⟩

/-- Helper: `n` trades climb progress by `n` whenever `held ≥ n` and there is
    room (`progress + n ≤ total`). Generalizes `replicate_trade_accounts` to
    `held ≥ n` (only `n` items get consumed; surplus held is untouched). -/
theorem replicate_trade_progress_of_room :
    ∀ (n : Nat) (s : RunState),
      n ≤ s.held → s.progress + n ≤ s.total →
        (applyRun s (List.replicate n trade)).progress = s.progress + n := by
  intro n
  induction n with
  | zero =>
    intro s _ _
    simp [applyRun]
  | succ k ih =>
    intro s hHeld hRoom
    show (applyRun s (trade :: List.replicate k trade)).progress = s.progress + (k + 1)
    rw [applyRun_cons]
    have hFire : 0 < s.held ∧ s.progress < s.total := by
      constructor <;> omega
    have hCons := trade_consumes s hFire
    have hTot : (trade s).total = s.total := by
      unfold trade; rw [if_pos hFire]
    have hHeld' : k ≤ (trade s).held := by rw [hCons.1]; omega
    have hRoom' : (trade s).progress + k ≤ (trade s).total := by
      rw [hCons.2, hTot]; omega
    rw [ih (trade s) hHeld' hRoom', hCons.2]
    omega

/-! ## REACHABILITY -/

/-- **REACHABILITY** — from `progress = p < total`, the plan
    `obtain (total - p)` followed by `(total - p)` trades reaches
    `progress = total`. The witness `N = total - p` is strictly positive
    (`p < total`), and every trade in the tail fires because `obtain`
    front-loaded exactly `N` held items — the coupling makes this
    reachability witness load-bearing, not free. -/
theorem obtain_then_trades_reach (s : RunState) (h : s.progress < s.total) :
    let N := s.total - s.progress
    (applyRun (obtain s N) (List.replicate N trade)).progress = s.total := by
  intro N
  -- After obtain N: held = s.held + N, progress = s.progress, total = s.total.
  -- Every trade in the N-step tail fires because obtain front-loaded N items;
  -- only N of the held items get consumed (use the held ≥ N helper).
  have hoHeld : (obtain s N).held = s.held + N := rfl
  have hoProg : (obtain s N).progress = s.progress := rfl
  have hoTot : (obtain s N).total = s.total := rfl
  have key := replicate_trade_progress_of_room N (obtain s N)
    (by rw [hoHeld]; omega) (by rw [hoProg, hoTot]; omega)
  rw [key, hoProg]
  omega

/-- **REACHABILITY (existential form)** — there exists a plan
    (`obtain N` prefix ++ `N` trades) that reaches `progress = total`. -/
theorem obtain_then_trades_reach_exists (s : RunState)
    (h : s.progress < s.total) :
    ∃ (N : Nat) (plan : List (RunState → RunState)),
      N = s.total - s.progress
      ∧ plan = (fun t => obtain t N)
                 :: List.replicate N trade
      ∧ (applyRun s plan).progress = s.total := by
  refine ⟨s.total - s.progress,
          (fun t => obtain t (s.total - s.progress))
            :: List.replicate (s.total - s.progress) trade,
          rfl, rfl, ?_⟩
  rw [applyRun_cons]
  exact obtain_then_trades_reach s h

/-! ## THE KEY NON-VACUITY WITNESS: held accounting -/

/-- **NON-VACUITY (held accounting)** — the WHOLE run consumes EXACTLY the
    items obtained. Starting from `held = 0` and `progress = p < total`,
    `obtain (total - p)` then `(total - p)` trades ends with `held = 0` and
    `progress = total`.

    This is the theorem the rejected capstone could not state: progress reaches
    total ONLY by consuming every obtained item (no free progress). `obtain`
    and `trade` are inventory-coupled; the net inventory change is zero and the
    net progress change is exactly the items obtained. -/
theorem held_accounts (s : RunState)
    (hHeld0 : s.held = 0) (h : s.progress < s.total) :
    let N := s.total - s.progress
    (applyRun (obtain s N) (List.replicate N trade)).held = 0
    ∧ (applyRun (obtain s N) (List.replicate N trade)).progress = s.total := by
  intro N
  -- obtain N from a fresh (held = 0) inventory loads exactly N held items.
  have hoHeld : (obtain s N).held = N := by
    show s.held + N = N; rw [hHeld0]; omega
  have hoProg : (obtain s N).progress = s.progress := rfl
  have hoTot : (obtain s N).total = s.total := rfl
  -- held = N exactly and progress + N = total, so every trade fires and held
  -- drains to 0.
  have hRoom : (obtain s N).progress + N ≤ (obtain s N).total := by
    rw [hoProg, hoTot]; omega
  obtain ⟨accP, accH, _⟩ := replicate_trade_accounts N (obtain s N) hoHeld hRoom
  refine ⟨?_, ?_⟩
  · rw [accH, hoHeld]; omega
  · rw [accP, hoProg]; omega

/-! ## Concrete witness -/

/-- Canonical entry state: nothing held, no progress, 3 units required. -/
def witnessStart : RunState := { held := 0, progress := 0, total := 3 }

/-- The plan: obtain 3, then trade three times. -/
def witnessRun : RunState :=
  applyRun (obtain witnessStart 3) (List.replicate 3 trade)

-- `#eval` witness — obtain 3 then trade thrice → held = 0, progress = 3.
#eval witnessRun   -- { held := 0, progress := 3, total := 3 }

/-- Concrete non-vacuity example: the witness run ends `held = 0, progress = 3`
    (every obtained item consumed; progress reaches total). Checked by `rfl`. -/
example : witnessRun = { held := 0, progress := 3, total := 3 } := by
  rfl

/-- The witness is exactly the `held_accounts` instance at `p = 0, total = 3`:
    `held = 0` (every obtained item consumed) and `progress = total`. The
    `held_accounts` theorem yields these facts; here we confirm they hold
    concretely (computable, closed by `decide`). -/
example :
    witnessRun.held = 0 ∧ witnessRun.progress = witnessStart.total := by
  have hacc := held_accounts witnessStart (by rfl) (by decide)
  -- hacc : (applyRun (obtain witnessStart 3) (replicate 3 trade)).held = 0 ∧ ….progress = 3
  exact hacc

end Formal.Liveness.ItemsTaskRun
