/-
  Formal.Liveness.Measure

  Lexicographic measure function over the planner's projected `State`.

  Phase-19b deliverable #1 (see `docs/PLAN_liveness.md`, Phase 19 / M4).
  Phase-19c extends the measure from a 5-tuple to a **6-tuple** so that
  `GatherAction`'s progress (which only increments a per-skill XP counter)
  can be observed as a measure decrease. The change is forced by Gather's
  semantics: it does NOT advance `task_progress` (the production comment at
  `gathering.py:59` explains why only `TaskTradeAction` increments task
  progress), and it INCREASES `inventory_used` (a drop is added). Therefore
  Gather progresses only via a per-skill XP delta — that signal must live
  in the measure ABOVE `bankPressure`, so Deposit (which drops bank
  pressure independently) can fire when needed without violating the
  decrease invariant.

  Components, ordered most significant first (slot index in parens):

    (1) levelDeficit             : 50 - state.level
    (2) xpDeficit                : xpToNext - state.xp
    (3) taskCycles               : taskTotal - taskProgress
    (4) skillXpDeficitProjected  : targetSkillXp - projectedSkillXpDelta
        (NEW in 19c — decreases on Gather)
    (5) bankPressure             : max(0, inventoryUsed - 4 * inventoryMax / 5)
        (decreases on Deposit; Gather may INCREASE it, dominated by slot 4)
    (6) hpDeficit                : maxHp - hp
        (decreases on Rest; Fight may INCREASE it, dominated by slot 2)

  Mathlib is permitted in this namespace per the Phase-19a axiom split.
  We use Mathlib's `Prod.Lex` and well-foundedness instances.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Mathlib.Order.WellFounded
import Mathlib.Data.Prod.Lex
import Formal.Liveness.TaskLifecyclePhase

set_option linter.dupNamespace false

namespace Formal.Liveness.Measure

open Formal.Liveness.TaskLifecyclePhase

/-! ## Planner-side state model

A minimal `State` mirroring exactly the fields the Phase-19b/c action lemmas
read or write. This is NOT a faithful image of `src/.../world_state.py`'s
`WorldState`; it deliberately omits coordinates, equipment, bank items, and
cooldown — those are irrelevant to the local-progress measure.

Field names use Lean conventions (camelCase). Each maps one-to-one onto a
`WorldState` field (snake_case), documented inline.

Phase 19c adds two scalar fields for the single-skill MVP of
`projected_skill_xp_delta` / the active LevelSkillGoal's target:

  * `projectedSkillXpDelta` — single-skill scalar of
    `WorldState.projected_skill_xp_delta[skill]` for the currently-tracked
    skill. The dict is collapsed to a scalar because the headline lemma
    operates on a single (drop, skill) pair.
  * `targetSkillXp` — the active `LevelSkillGoal`'s target xp for that
    skill. State-carried (NOT a new axiom). When no LevelSkillGoal is
    active, callers pass `0` and the slot is a no-op (deficit is `0 - 0 = 0`).
-/

/-- Planner-side projected state. Mirrors only the WorldState fields used by
    the Phase-19b/c progress lemmas. -/
structure State where
  /-- `WorldState.level`. -/
  level         : Nat
  /-- `WorldState.xp`. -/
  xp            : Nat
  /-- `WorldState.task_progress`. -/
  taskProgress  : Nat
  /-- `WorldState.task_total`. -/
  taskTotal     : Nat
  /-- `WorldState.inventory_used` (the sum of stack quantities). -/
  inventoryUsed : Nat
  /-- `WorldState.inventory_max`. -/
  inventoryMax  : Nat
  /-- `WorldState.hp`. -/
  hp            : Nat
  /-- `WorldState.max_hp`. -/
  maxHp         : Nat
  /-- `WorldState.task_type` — `"monsters" | "resources" | "crafting"`. -/
  taskType      : Option String
  /-- `WorldState.task_code`. -/
  taskCode      : Option String
  /-- Single-skill scalar of `WorldState.projected_skill_xp_delta[skill]`
      for the currently-tracked skill. See module docstring. -/
  projectedSkillXpDelta : Nat
  /-- Active `LevelSkillGoal`'s target xp for the tracked skill. Pass `0`
      when no such goal is active (slot becomes a no-op). -/
  targetSkillXp : Nat
  -- Phase 20a-v2 extensions — fields read by the production ladder.
  -- These fields exist solely to let `Formal.Liveness.ProductionLadder.fires`
  -- mirror the production `_fires_*` predicates in `tiers/guards.py` /
  -- `tiers/means.py`. Tier-1 apply functions (Fight/Gather/Deposit/Rest)
  -- PRESERVE every one of these fields via `{ s with ... }` — none are
  -- mutated by Phase-19 progress actions.
  --
  -- Several fields are OPAQUE Bools — they carry production's observed
  -- answer for a predicate the Lean model can't readily reproduce (e.g.
  -- `task_decision == PIVOT`, `low_yield_cancel_fires`). They are NOT
  -- axioms; they are state-carried observations. A later diff harness
  -- must assert the Bool matches the production computation.
  /-- `WorldState.gold`. Read by BANK_EXPAND. -/
  gold : Nat
  /-- ctx flag `SelectionContext.bank_accessible` (guards.py:26). -/
  bankAccessible : Bool
  /-- ctx flag — `ctx.bank_unlock_monster is not None` (guards.py:28). -/
  bankUnlockMonsterPresent : Bool
  /-- ctx — `SelectionContext.initial_xp` (guards.py:29). -/
  initialXp : Nat
  /-- `game_data.monster_level(ctx.bank_unlock_monster)`; `0` if unknown
      (guards.py:74). -/
  unlockMonsterLevel : Nat
  /-- ctx — `SelectionContext.bank_required_level` (guards.py:27). -/
  bankRequiredLevel : Nat
  /-- `bool(overstocked_items(state, game_data))` (guards.py:82, 87). -/
  hasOverstockItems : Bool
  /-- `bool(select_bank_deposits(state, game_data))` — opaque
      (guards.py:85). -/
  selectBankDepositsNonempty : Bool
  /-- `bool(state.pending_items)` (means.py:68). -/
  pendingItemsNonempty : Bool
  /-- `_has_sellable(state, game_data)` (means.py:54-58). -/
  sellableInventoryNonempty : Bool
  /-- `_tasks_coin_total(state)` (means.py:61-62): inventory + bank. -/
  taskCoinsTotal : Nat
  /-- ctx — `SelectionContext.task_exchange_min_coins` (guards.py:30). -/
  taskExchangeMinCoins : Nat
  /-- OPAQUE: `low_yield_cancel_fires(state, history)` (means.py:78). -/
  lowYieldCancelFires : Bool
  /-- OPAQUE: `task_decision(state, game_data, history) == PIVOT`, with
      gating `bool(state.task_code) and history is not None` already
      folded in (means.py:80-83). -/
  taskCancelFires : Bool
  /-- OPAQUE: production's PURSUE_TASK predicate (means.py:85-90), with
      all gating folded in (`task_type == "items"`, `task_code`,
      `task_progress < task_total`, `history is not None`,
      `task_decision == PURSUE`). -/
  pursueTaskFires : Bool
  /-- OPAQUE: production's objective-step firing predicate (the
      StrategyArbiter inserts the StepGoal candidate iff the objective
      tier yields a plannable step). -/
  objectiveStepFires : Bool
  /-- `state.bank_items is not None` (means.py:104). -/
  bankItemsKnown : Bool
  /-- `len(state.bank_items)` when known, else `0` (means.py:108). -/
  bankItemsCount : Nat
  /-- `game_data._bank_capacity` (means.py:106, 108). -/
  bankCapacity : Nat
  /-- `game_data._next_expansion_cost` (means.py:111). -/
  nextExpansionCost : Nat
  /-- Phase 23c-3b: lifecycle phase mirror of
      `WorldState.task_lifecycle_phase` (production:
      `src/artifactsmmo_cli/ai/task_lifecycle.py`). The phase is
      INTENDED to satisfy
        `taskLifecyclePhase = deriveTaskLifecyclePhase taskCode taskProgress taskTotal`
      for every state produced via the canonical constructors;
      `taskPhase_consistent` documents this as a separate hypothesis
      (NOT a Prop field on the structure, per Phase 23b's cascade
      lesson). Callers constructing `State` directly bear the obligation
      to set `taskLifecyclePhase` consistently. -/
  taskLifecyclePhase : TaskLifecyclePhase
  /-- Phase 23d-4: cumulative count of action attempts on the current
      task. Incremented by `applyActionKind` on every progress-attempting
      action (`.fight`, `.taskTrade`) while the pre-state phase is
      `.accepted` or `.inProgress`. Reset to `0` on transitions to
      `.none` (via `.completeTask` and `.taskCancel`). Other action
      kinds preserve the counter (via `{s with ...}`).

      Honest disclosure: production's `low_yield_cancel_fires` reads
      `sample_count` from `LearningStore.farm_items_yield`, which is
      recorded per completed cycle of FarmItems-like behaviour (see
      `src/artifactsmmo_cli/ai/learning/projections.py`). This counter
      is a simpler abstraction — it increments per any progress-
      attempting action while a task is active. A future differential
      harness must assert that production's `sample_count` tracks this
      Lean field within model fidelity. The production constant
      `LOW_YIELD_SAMPLE_THRESHOLD` maps to `lowYieldSampleThreshold`
      in `Formal.Liveness.LIV003Decomposition`.

      The counter is NOT part of the lex `Measure` tuple — keeping it
      out of `Measure`/`ExtMeasure` preserves Phase-19 lemmas
      mechanically (they `{s with ...}` over State, so the new field
      is automatically threaded through). -/
  actionsAttempted : Nat
  /-- Phase 23d-8: counter of completed `.craft` applies. Abstract
      counter for recipe-chain closure proofs. Production's
      `CraftAction.apply` composes inventory updates + skill XP delta +
      task progress; the Lean model abstracts these to a single
      counter advance per `.craft` step. -/
  craftableSlots : Nat
  /-- Perimeter Item 1a: production's `task_decision == PIVOT` reads
      LearningStore observations + skill XP curve confidence to decide
      whether the current task is worth pursuing. The Lean model
      abstracts this to a single Bool: `true` when production would
      decide PURSUE (lifecycle progresses toward `.complete`), `false`
      when production would decide PIVOT (lifecycle exits via cancel).
      Required to prove `accept_cancel_loop_bound` structurally — the
      .accepted → cycleStep transition only proceeds toward .complete
      when this is true; otherwise taskCancelFires would trigger early
      and re-enter the .none → .accepted cycle indefinitely. -/
  taskFeasibleProjected : Bool
  /-- Item 1g-A1: model the API's task-code pool. The server's
      `/v3/my/tasks/new` endpoint draws from a finite pool of distinct
      codes (game_data.task_codes). `taskPool` records that pool's
      contents from the Lean side.

      Defaults to the empty list in legacy fixtures — existing
      proofs that don't reason about pool depletion remain green.
      The discharge of `accept_cancel_loop_bound` (Item 1g-A2) requires
      callers to populate `taskPool` from `GameDataFixture`. -/
  taskPool : List String
  /-- Item 1g-A1: codes the bot has already cancelled. Each
      `.taskCancel` apply pushes the current `taskCode` onto this list
      (subject to extension in Item 1g-A2). Pigeonhole: when
      `taskCodesSeen.length ≥ taskPool.length`, the next `.acceptTask`
      cannot pick a fresh code and either rides to `.complete` or the
      pool refresh applies. -/
  taskCodesSeen : List String
  deriving Repr

namespace State

/-- Mirrors `WorldState.inventory_free` (Nat sub saturates at 0). -/
def inventoryFree (s : State) : Nat := s.inventoryMax - s.inventoryUsed

/-- HP-percent comparison expressed without floats, matching
    `state.hp_percent > 3 / 10` (the `_MIN_FIGHT_HP_FRACTION = 0.3` test in
    `combat.py`). With `max_hp == 0` we treat HP as zero (Python returns
    `0.0` then). The strict inequality `hp / max_hp > 3 / 10` is equivalent
    (in `Rat`) to `10 * hp > 3 * max_hp`; we use this Nat form throughout. -/
def hpAboveMinFightFraction (s : State) : Bool :=
  decide (s.maxHp > 0) && decide (10 * s.hp > 3 * s.maxHp)

end State

/-! ## Server-curve axiom

`xpToNextLevel L` is the server's xp threshold to advance from level `L` to
`L+1`. The exact curve lives server-side; the openapi `/v3/server/details`
endpoint exposes it. We don't model the curve concretely yet (Phase 24's
GameDataFixture is the place for that). For Phase 19b we only need:

  * `xpToNextLevel L > 0` for every `L < 50` — i.e. there is always a
    positive xp budget remaining before max level. This is structurally
    obvious for any sensible curve (a level transition that requires zero
    xp would mean the level doesn't exist), but it is empirically a
    statement about the server response, not a theorem, so it enters as
    an axiom.

AXIOM-ID: LIV-001 | spec: /v3/server/details (xp_curve) | introduced: 2026-05-30
-/

/-- Server-side xp threshold to advance from level `L` to level `L+1`. -/
axiom xpToNextLevel : Nat → Nat

/-- For every level strictly below the cap (50), the xp budget remaining
    is positive. See AXIOM-ID LIV-001 above for openapi citation. -/
axiom xpToNextLevel_pos : ∀ L, L < 50 → xpToNextLevel L > 0

/-! ## LIV-002 — CompleteTask planner-side XP grant

  LIV-002 (user-approved 2026-06-03 — value revised from 10 → 0)

  Planner-side projection: `CompleteTaskAction.apply` grants
  `TASK_COMPLETE_XP_ESTIMATE = 0` xp per completion. The server
  endpoint `/action/task/complete` returns a `RewardsSchema` whose
  fields are `items` and `gold` only — there is NO XP field. Character
  XP changes during the per-cycle progress actions (fight/gather),
  not at turn-in. The 2026-06-01 value (10) was an empirical guess
  that has since been falsified by direct observation; this `def` is
  the corrected planner constant.

  OpenAPI citation:
    `artifactsmmo-api-client/artifactsmmo_api_client/models/rewards_schema.py`
    — `RewardsSchema.{items: list[SimpleItemSchema], gold: int}`.
  Production reference:
    `src/artifactsmmo_cli/ai/actions/complete_task.py` —
    `TASK_COMPLETE_XP_ESTIMATE: int = 0`.

  Downstream proofs (`LIV003Decomposition.lifecycle_progress_from_bounds_step`,
  `LifecycleBound3/4`) remain structurally correct: the xp-grant
  disjunct now witnesses `xp = s.xp + 0`, and the rollover branch in
  `Plan.applyActionKind .completeTask` becomes dead under LIV-001
  (`xpToNextLevel L > 0` at `L < 50`, so `s.xp + 0 ≥ xpToNextLevel s.level`
  cannot hold under the invariant `s.xp < xpToNextLevel s.level`). -/
def taskCompleteXpEstimate : Nat := 0

/-! ## Task lifecycle phase consistency

The `taskLifecyclePhase` field on `State` is intended to be derivable
from `taskCode`, `taskProgress`, `taskTotal`. The intent is documented
here as a Prop, NOT enforced as a Prop field on `State` (per Phase 23b's
cascade lesson). Callers using the canonical constructors are responsible
for maintaining the predicate. -/

/-- Consistency predicate. Bundles three production invariants:

    1. `taskLifecyclePhase` matches `deriveTaskLifecyclePhase` over the
       raw task fields. Mirrors `WorldState.__post_init__`'s assertion.

    2. `taskCode ≠ some ""`. Production's `WorldState` normalizes empty
       task codes to `None` (see `world_state.py` post-init); only
       `none` or a non-empty `some _` ever occur in reached states.
       CompleteTaskAction transiently sets `task_code=""` but the
       perception layer normalizes that before the next cycle.

    3. `taskCode.isSome → taskTotal > 0`. Production: a real task always
       has positive total; the API never returns `task_code` set with
       `task_total = 0`. -/
def taskPhaseConsistent (s : State) : Prop :=
  s.taskLifecyclePhase =
    Formal.Liveness.TaskLifecyclePhase.deriveTaskLifecyclePhase
      s.taskCode s.taskProgress s.taskTotal
  ∧ s.taskCode ≠ some ""
  ∧ (s.taskCode.isSome → s.taskTotal > 0)

/-! ## Measure tuple -/

/-- Lex-tuple measure. Smaller = closer to level 50. Lex order is by
    field declaration order (level first, hp last). -/
structure Measure where
  /-- `50 - state.level`. -/
  levelDeficit : Nat
  /-- `xpToNextLevel state.level - state.xp`. -/
  xpDeficit    : Nat
  /-- `state.taskTotal - state.taskProgress`. -/
  taskCycles   : Nat
  /-- `state.targetSkillXp - state.projectedSkillXpDelta`. NEW in 19c. -/
  skillXpDeficitProjected : Nat
  /-- `max 0 (state.inventoryUsed - state.inventoryMax * 4 / 5)`. -/
  bankPressure : Nat
  /-- `state.maxHp - state.hp`. -/
  hpDeficit    : Nat
  deriving DecidableEq, Repr

/-- Bank-pressure threshold: 80 % of inventory capacity. Mirrors
    `DEPOSIT_FULL_FRACTION = 0.80` in
    `src/artifactsmmo_cli/ai/tiers/guards.py`. -/
def bankPressureThreshold (inventoryMax : Nat) : Nat := inventoryMax * 4 / 5

/-- Extract the measure tuple from a `State`. `noncomputable` because
    `xpToNextLevel` is axiomatic — only the proof-time projection is needed. -/
noncomputable def measure (s : State) : Measure :=
  { levelDeficit := 50 - s.level
    xpDeficit    := xpToNextLevel s.level - s.xp
    taskCycles   := s.taskTotal - s.taskProgress
    skillXpDeficitProjected := s.targetSkillXp - s.projectedSkillXpDelta
    bankPressure := s.inventoryUsed - bankPressureThreshold s.inventoryMax
    hpDeficit    := s.maxHp - s.hp }

/-! ## Lex strict order

Hand-rolled six-way disjunction: at the first index where the tuples
differ, the smaller component wins. -/

/-- Strict lex order on `Measure`. -/
def measureLt (m₁ m₂ : Measure) : Prop :=
  m₁.levelDeficit < m₂.levelDeficit
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit < m₂.xpDeficit)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles < m₂.taskCycles)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected < m₂.skillXpDeficitProjected)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure < m₂.bankPressure)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure = m₂.bankPressure ∧ m₁.hpDeficit < m₂.hpDeficit)

/-! ### Well-foundedness

We reduce `measureLt` to the right-associated lex product over `Nat`, for
which Mathlib's `WellFoundedRelation` instance is automatic. -/

/-- Right-associated six-tuple of `Nat` for the embedding. -/
abbrev LexHex := Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat

/-- Embed a `Measure` into the right-associated lex six-tuple. -/
def toLexHex (m : Measure) : LexHex :=
  toLex (m.levelDeficit,
         toLex (m.xpDeficit,
                toLex (m.taskCycles,
                       toLex (m.skillXpDeficitProjected,
                              toLex (m.bankPressure, m.hpDeficit)))))

/-- `measureLt` implies the embedded `<` on `LexHex`.

    This is enough to inherit well-foundedness via `Subrelation.wf`. We do
    NOT prove the reverse direction (the iff) because it isn't needed and
    the encoding is painful in Mathlib's `Prod.Lex` `ofLex`/`toLex` forms. -/
theorem toLexHex_lt_of_measureLt
    {m₁ m₂ : Measure} (h : measureLt m₁ m₂) :
    toLexHex m₁ < toLexHex m₂ := by
  simp only [toLexHex, Prod.Lex.lt_iff, ofLex_toLex]
  rcases h with h | ⟨he₁, h⟩ | ⟨he₁, he₂, h⟩ | ⟨he₁, he₂, he₃, h⟩
              | ⟨he₁, he₂, he₃, he₄, h⟩ | ⟨he₁, he₂, he₃, he₄, he₅, h⟩
  · exact Or.inl h
  · exact Or.inr ⟨he₁, Or.inl h⟩
  · exact Or.inr ⟨he₁, Or.inr ⟨he₂, Or.inl h⟩⟩
  · exact Or.inr ⟨he₁, Or.inr ⟨he₂, Or.inr ⟨he₃, Or.inl h⟩⟩⟩
  · exact Or.inr ⟨he₁, Or.inr ⟨he₂, Or.inr ⟨he₃, Or.inr ⟨he₄, Or.inl h⟩⟩⟩⟩
  · exact Or.inr ⟨he₁, Or.inr ⟨he₂, Or.inr ⟨he₃, Or.inr ⟨he₄, Or.inr ⟨he₅, h⟩⟩⟩⟩⟩

/-- `measureLt` is well-founded — the foundation needed for later
    termination arguments (Phase 23). -/
theorem measureLt_wellFounded : WellFounded measureLt := by
  have hwf : WellFounded (fun a b : LexHex => a < b) :=
    (inferInstance : WellFoundedRelation LexHex).wf
  exact Subrelation.wf
    (h₁ := fun {a b} h => toLexHex_lt_of_measureLt h)
    (InvImage.wf toLexHex hwf)

/-! ## Key step lemmas — used by the per-action progress proofs -/

/-- A strict decrease in the primary component (levelDeficit) dominates the
    lex order regardless of the lower components. -/
theorem measureLt_of_levelDeficit_dec
    {m₁ m₂ : Measure} (h : m₁.levelDeficit < m₂.levelDeficit) :
    measureLt m₁ m₂ := Or.inl h

/-- Within a fixed level, a strict decrease in `xpDeficit` decreases the
    measure. -/
theorem measureLt_of_xpDeficit_dec
    {m₁ m₂ : Measure}
    (heq : m₁.levelDeficit = m₂.levelDeficit)
    (h : m₁.xpDeficit < m₂.xpDeficit) :
    measureLt m₁ m₂ := Or.inr (Or.inl ⟨heq, h⟩)

/-- Within fixed `levelDeficit`, `xpDeficit`, `taskCycles`, a strict decrease
    in `skillXpDeficitProjected` (slot 4) decreases the measure. -/
theorem measureLt_of_skillXpDeficit_dec
    {m₁ m₂ : Measure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit    = m₂.xpDeficit)
    (h3 : m₁.taskCycles   = m₂.taskCycles)
    (h  : m₁.skillXpDeficitProjected < m₂.skillXpDeficitProjected) :
    measureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inl ⟨h1, h2, h3, h⟩)))

/-- Within fixed `levelDeficit`, `xpDeficit`, `taskCycles`,
    `skillXpDeficitProjected`, a strict decrease in `bankPressure`
    (slot 5) decreases the measure. -/
theorem measureLt_of_bankPressure_dec
    {m₁ m₂ : Measure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit    = m₂.xpDeficit)
    (h3 : m₁.taskCycles   = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h  : m₁.bankPressure < m₂.bankPressure) :
    measureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨h1, h2, h3, h4, h⟩))))

/-- Within fixed slots 1-5, a strict decrease in `hpDeficit` (slot 6)
    decreases the measure. -/
theorem measureLt_of_hpDeficit_dec
    {m₁ m₂ : Measure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit    = m₂.xpDeficit)
    (h3 : m₁.taskCycles   = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h5 : m₁.bankPressure = m₂.bankPressure)
    (h  : m₁.hpDeficit < m₂.hpDeficit) :
    measureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr ⟨h1, h2, h3, h4, h5, h⟩))))

end Formal.Liveness.Measure
