/-
  Formal.Liveness.Reachable

  Phase-20a deliverable #1 (see `docs/PLAN_liveness.md`, Phase 20). An
  inductive `Reachable : State → Prop` capturing the set of planner-side
  states the AI can reach from a concrete spawn witness by repeated
  application of `Formal.Liveness.ProgressAction.applyAction`.

  ## Design

  * Spawn is a CONCRETE witness (level 1, full HP, no task, empty
    inventory, no pending items, bank not locked, no level-blocker).
    Phase 25 will generalise spawn variation if needed.
  * The closure step is keyed on `actionIsApplicable s a = true` AND
    `validInvariants s a` — both are load-bearing in the Phase-19
    progress lemmas. Carrying both into the `Reachable` closure is the
    HONEST choice (per `feedback_proofs_tell_false_stories`): if we drop
    `validInvariants` here, Phase 22's perception-invariant gap re-opens
    as a Reachable-but-no-progress state. We pay that cost up front.

  ## Out of scope here (deferred to Phase 20b)

  * The headline `∀ s, Reachable s → ∃ g, g.value s > 0`.
  * Non-`ProgressAction` actions (Move, Equip, Withdraw, Craft, NpcBuy,
    NpcSell, TaskAccept, TaskCancel, TaskTrade, ClaimPending). These
    preserve the measure (per Phase 19c disclosure) and are excluded from
    the Reachable closure for Phase 20a. Including them does not break
    no-deadlock (regions still cover all states reached so far), but
    they ALSO don't enable any new state shape relevant to the regions
    below — every Phase-18 firing input is touched by the four Tier-1
    actions or is independent of them. Phase 20b/21 will extend the
    closure as needed.

  Liveness namespace — Mathlib axioms allowed (see
  `Formal/Liveness/README.md`).
-/
import Formal.Liveness.Measure
import Formal.Liveness.ProgressAction

set_option linter.dupNamespace false

namespace Formal.Liveness.Reachable

open Formal.Liveness.Measure
open Formal.Liveness.ProgressAction

/-! ## Concrete spawn witness

Mirrors a fresh character with no task, full HP, empty inventory, and no
unlock or pending-items obligation. Numeric constants:

  * `level = 1`, `xp = 0` — fresh character start.
  * `taskTotal = 0`, `taskProgress = 0`, `taskType = none`,
    `taskCode = none` — no active task.
  * `inventoryUsed = 0`, `inventoryMax = 100` — production default
    bank slot count for a fresh character (matches the L1 inventory cap
    in `WorldState`).
  * `hp = maxHp = 100` — at full health.
  * `projectedSkillXpDelta = 0`, `targetSkillXp = 0` — no LevelSkillGoal.
  * `pendingItems = false`, `bankLocked = false`, `bankXpExceeded = false`,
    `bankUnreachable = false`, `unlockTargetLevel = 0` — pristine bank /
    unlock state. -/
def spawnState : State :=
  { level := 1
    xp := 0
    taskProgress := 0
    taskTotal := 0
    inventoryUsed := 0
    inventoryMax := 100
    hp := 100
    maxHp := 100
    taskType := none
    taskCode := none
    projectedSkillXpDelta := 0
    targetSkillXp := 0
    pendingItems := false
    bankLocked := false
    bankXpExceeded := false
    bankUnreachable := false
    unlockTargetLevel := 0 }

/-! ## Inductive closure

`Reachable s` ↔ `s` is the spawn state OR `s` arises by applying an
applicable `ProgressAction` (with its productivity invariants
satisfied) to a Reachable predecessor. -/
inductive Reachable : State → Prop
  | spawn : Reachable spawnState
  | step  : ∀ {s : State} (a : ProgressAction),
              Reachable s →
              actionIsApplicable s a = true →
              validInvariants s a →
              Reachable (applyAction s a)

/-- Sanity: the spawn witness is reachable. -/
theorem spawn_reachable : Reachable spawnState := Reachable.spawn

end Formal.Liveness.Reachable
