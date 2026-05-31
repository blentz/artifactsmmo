/-
  Formal.Liveness.Measure

  Lexicographic measure function over the planner's projected `State`.

  Phase-19b deliverable #1 (see `docs/PLAN_liveness.md`, Phase 19 / M4).
  Defines a five-component lex tuple that orders states from "further from
  level 50" to "closer". Per-action progress lemmas (Phase 19b onward) show
  individual actions strictly decrease this measure (or trigger level-up,
  which dominates lex-order via the primary component).

  Components, ordered most significant first:
    1. levelDeficit : 50 - state.level     (decreases on level-up)
    2. xpDeficit    : xpToNext - state.xp  (decreases on combat / xp-grant)
    3. taskCycles   : taskTotal - taskProgress (decreases on task-match)
    4. bankPressure : max(0, inventoryUsed - 4 * inventoryMax / 5)
       (decreases on deposit)
    5. hpDeficit    : maxHp - hp           (decreases on restore; Fight
       INCREASES this — handled by lex order, since combat decreases
       higher-priority `xpDeficit`).

  Mathlib is permitted in this namespace per the Phase-19a axiom split.
  We use Mathlib's `Prod.Lex` and well-foundedness instances.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Mathlib.Order.WellFounded
import Mathlib.Data.Prod.Lex

set_option linter.dupNamespace false

namespace Formal.Liveness.Measure

/-! ## Planner-side state model

A minimal `State` mirroring exactly the fields the Phase-19b action lemmas
read or write. This is NOT a faithful image of `src/.../world_state.py`'s
`WorldState`; it deliberately omits coordinates, equipment, bank items, and
cooldown — those are irrelevant to the local-progress measure.

Field names use Lean conventions (camelCase). Each maps one-to-one onto a
`WorldState` field (snake_case), documented inline.
-/

/-- Planner-side projected state. Mirrors only the WorldState fields used by
    the Phase-19b progress lemmas. -/
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
    bankPressure := s.inventoryUsed - bankPressureThreshold s.inventoryMax
    hpDeficit    := s.maxHp - s.hp }

/-! ## Lex strict order

Hand-rolled five-way disjunction: at the first index where the tuples
differ, the smaller component wins. -/

/-- Strict lex order on `Measure`. -/
def measureLt (m₁ m₂ : Measure) : Prop :=
  m₁.levelDeficit < m₂.levelDeficit
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit < m₂.xpDeficit)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles < m₂.taskCycles)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles ∧ m₁.bankPressure < m₂.bankPressure)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles ∧ m₁.bankPressure = m₂.bankPressure
     ∧ m₁.hpDeficit < m₂.hpDeficit)

/-! ### Well-foundedness

We prove `measureLt` well-founded by reducing to a measure on a strictly
bounded natural number: `weight(m) = ((((L*K + X)*K + T)*K + B)*K + H)`
where `K` is a placeholder bound. Since Mathlib's `Nat` lex-on-product is
WF, we instead use a five-fold nested measure via `WellFounded.recursion`
on `levelDeficit` (Nat-WF) with an inner WF on the remaining tuple.

The cleanest route is via `Subrelation.wf` from a function into
`Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat` — Mathlib proves the right-associated
lex-on-`Nat` product well-founded automatically. -/

/-- Right-associated five-tuple of `Nat` for the embedding. -/
abbrev LexQuint := Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat

/-- Embed a `Measure` into the right-associated lex quint. -/
def toLexQuint (m : Measure) : LexQuint :=
  toLex (m.levelDeficit,
         toLex (m.xpDeficit,
                toLex (m.taskCycles,
                       toLex (m.bankPressure, m.hpDeficit))))

/-- `measureLt` implies the embedded `<` on `LexQuint`.

    This is enough to inherit well-foundedness via `Subrelation.wf`. We do
    NOT prove the reverse direction (the iff) because it isn't needed and
    the encoding is painful in Mathlib's `Prod.Lex` `ofLex`/`toLex` forms. -/
theorem toLexQuint_lt_of_measureLt
    {m₁ m₂ : Measure} (h : measureLt m₁ m₂) :
    toLexQuint m₁ < toLexQuint m₂ := by
  simp only [toLexQuint, Prod.Lex.lt_iff, ofLex_toLex]
  rcases h with h | ⟨he₁, h⟩ | ⟨he₁, he₂, h⟩ | ⟨he₁, he₂, he₃, h⟩
              | ⟨he₁, he₂, he₃, he₄, h⟩
  · exact Or.inl h
  · exact Or.inr ⟨he₁, Or.inl h⟩
  · exact Or.inr ⟨he₁, Or.inr ⟨he₂, Or.inl h⟩⟩
  · exact Or.inr ⟨he₁, Or.inr ⟨he₂, Or.inr ⟨he₃, Or.inl h⟩⟩⟩
  · exact Or.inr ⟨he₁, Or.inr ⟨he₂, Or.inr ⟨he₃, Or.inr ⟨he₄, h⟩⟩⟩⟩

/-- `measureLt` is well-founded — the foundation needed for later
    termination arguments (Phase 23). -/
theorem measureLt_wellFounded : WellFounded measureLt := by
  have hwf : WellFounded (fun a b : LexQuint => a < b) :=
    (inferInstance : WellFoundedRelation LexQuint).wf
  exact Subrelation.wf
    (h₁ := fun {a b} h => toLexQuint_lt_of_measureLt h)
    (InvImage.wf toLexQuint hwf)

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

end Formal.Liveness.Measure
