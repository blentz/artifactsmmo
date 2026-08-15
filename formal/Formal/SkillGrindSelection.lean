-- @concept: crafting, planner @property: safety, totality
/-
Role theorems for `skill_grind_selection_pure` (the recipe-aware skill-grind
target selector). Proved DIRECTLY on the extracted def (String-keyed in both
Python and Lean — no encoding bridge needed).

THE CONTRACT (why this exists): the live bot, committed to weaponcrafting, ground
gearcrafting because `skill_grind_target` picked an UNOBTAINABLE weaponcrafting
item whose GatherMaterials GOAP-failed, and the arbiter fell cross-skill. The
selector now considers ONLY same-skill, in-level, obtainable candidates. These
theorems prove the selected code (when non-empty) ALWAYS belongs to a candidate
that is same-skill ∧ in-level ∧ obtainable — the cross-skill outcome is
unrepresentable at the selection layer. `actionable` ties non-empty result to the
existence of a feasible candidate.

Core only — no mathlib. Fold induction.
-/
import Formal.Extracted.SkillGrindSelection

namespace Formal.SkillGrindSelection

open Extracted.SkillGrindSelection

/-- A candidate is FEASIBLE for `skill` at `level`: same craft skill, in level,
obtainable, and xp-positive. (The extracted fold's `continue` guard is exactly
its negation.)

`xp_positive` joined the conjunction on 2026-08-06: a rung whose craft pays no
skill xp (`Formal.SkillXpPositive`, the server's level_penalty band) can never
advance the skill it was selected to advance, so grinding it is a non-terminating
no-op. It is a FILTER and not a ranking key because no `acquire_steps` count can
redeem a rung that yields zero — see the Python core's docstring for the 14h
live livelock that ordering alone could not have fixed. -/
def feasible (skill : String) (level : Int) (c : GrindCandidate) : Prop :=
  c.craft_skill = skill ∧ c.craft_level ≤ level ∧ c.obtainable = true
    ∧ c.xp_positive = true

/-- The fold step used by `skill_grind_selection_pure` (matches the extracted
inline lambda). -/
def step (skill : String) (level : Int)
    (best : Option GrindCandidate) (c : GrindCandidate) : Option GrindCandidate :=
  if ((!(decide (c.craft_skill = skill))) || (decide (c.craft_level > level)) || (!c.obtainable)
      || (!c.xp_positive))
  then best
  else (if _beats c best then some c else best)

/-- The extracted selector's fold IS `List.foldl (step ...) none`. -/
theorem unfold_select (skill : String) (level : Int) (cands : List GrindCandidate) :
    skill_grind_selection_pure skill level cands
      = (match List.foldl (step skill level) none cands with
         | some c => c.code
         | none => "") := by
  unfold skill_grind_selection_pure step
  rfl

/-- When the guard is FALSE (the else-branch of `step` fires), the candidate is
feasible. -/
theorem guard_false_feasible (skill : String) (level : Int) (c : GrindCandidate)
    (hg : ((!(decide (c.craft_skill = skill))) || (decide (c.craft_level > level))
            || (!c.obtainable) || (!c.xp_positive)) = false) :
    feasible skill level c := by
  simp only [Bool.or_eq_false_iff, Bool.not_eq_eq_eq_not, Bool.not_false,
    decide_eq_true_eq, decide_eq_false_iff_not] at hg
  obtain ⟨⟨⟨hskill, hlevel⟩, hobt⟩, hxp⟩ := hg
  refine ⟨hskill, ?_, hobt, hxp⟩
  omega

/-- Structural characterization of `step`: its result is either the incoming
`best`, or `some d` with `d` feasible. -/
theorem step_cases (skill : String) (level : Int)
    (best : Option GrindCandidate) (d : GrindCandidate) :
    step skill level best d = best
      ∨ (step skill level best d = some d ∧ feasible skill level d) := by
  unfold step
  by_cases hg : ((!(decide (d.craft_skill = skill))) || (decide (d.craft_level > level))
            || (!d.obtainable) || (!d.xp_positive)) = true
  · rw [if_pos hg]; exact Or.inl rfl
  · rw [Bool.not_eq_true] at hg
    rw [if_neg (by rw [hg]; simp)]
    have hfeas := guard_false_feasible skill level d hg
    by_cases hb : _beats d best = true
    · rw [if_pos hb]; exact Or.inr ⟨rfl, hfeas⟩
    · rw [Bool.not_eq_true] at hb
      rw [if_neg (by rw [hb]; simp)]; exact Or.inl rfl

/-- FOLD INVARIANT: if the fold (from a feasible-or-none init) returns `some c`,
then `c` is feasible and a member of the processed list (or the init). -/
theorem fold_some_feasible (skill : String) (level : Int) :
    ∀ (cands : List GrindCandidate) (init : Option GrindCandidate),
      (∀ d, init = some d → feasible skill level d) →
      ∀ c, List.foldl (step skill level) init cands = some c →
        feasible skill level c ∧ (c ∈ cands ∨ init = some c) := by
  intro cands
  induction cands with
  | nil =>
    intro init hinit c h
    simp only [List.foldl_nil] at h
    exact ⟨hinit c h, Or.inr h⟩
  | cons d rest ih =>
    intro init hinit c h
    simp only [List.foldl_cons] at h
    -- acc is feasible-or-none: either it's `init` (feasible by hinit) or `some d`
    -- with d feasible (the else-branch only fires when d passes the guard).
    have hacc_inv : ∀ e, step skill level init d = some e → feasible skill level e := by
      intro e he
      rcases step_cases skill level init d with hstep | ⟨hstep, hfeas⟩
      · rw [hstep] at he; exact hinit e he
      · rw [hstep] at he; rw [Option.some.injEq] at he; exact he ▸ hfeas
    have hres := ih (step skill level init d) hacc_inv c h
    refine ⟨hres.1, ?_⟩
    rcases hres.2 with hmem | hinit_acc
    · exact Or.inl (List.mem_cons_of_mem _ hmem)
    · -- c came from acc = step init d; so c = d (∈ cons) or acc = init (Or.inr)
      rcases step_cases skill level init d with hstep | ⟨hstep, _⟩
      · rw [hstep] at hinit_acc; exact Or.inr hinit_acc
      · rw [hstep] at hinit_acc; rw [Option.some.injEq] at hinit_acc
        exact Or.inl (hinit_acc ▸ List.mem_cons_self)

/-- THE ROLE LEMMA: a non-empty selected code belongs to a feasible candidate. -/
theorem result_feasible (skill : String) (level : Int) (cands : List GrindCandidate)
    (h : skill_grind_selection_pure skill level cands ≠ "") :
    ∃ c, c ∈ cands ∧ c.code = skill_grind_selection_pure skill level cands
      ∧ feasible skill level c := by
  rw [unfold_select] at h ⊢
  cases hfold : List.foldl (step skill level) none cands with
  | none => simp [hfold] at h
  | some c =>
    have hfeas := fold_some_feasible skill level cands none (by simp) c hfold
    have hmem : c ∈ cands := by
      rcases hfeas.2 with hm | hcontra
      · exact hm
      · simp at hcontra
    exact ⟨c, hmem, rfl, hfeas.1⟩

/-- `grind_same_skill`: the selected code (when non-empty) is a candidate whose
craft_skill is the committed skill. NO cross-skill selection, ever. -/
theorem grind_same_skill (skill : String) (level : Int) (cands : List GrindCandidate)
    (h : skill_grind_selection_pure skill level cands ≠ "") :
    ∃ c, c ∈ cands ∧ c.code = skill_grind_selection_pure skill level cands
      ∧ c.craft_skill = skill := by
  obtain ⟨c, hm, hc, hf⟩ := result_feasible skill level cands h
  exact ⟨c, hm, hc, hf.1⟩

/-- `grind_in_level`: the selected candidate is craftable at the current level. -/
theorem grind_in_level (skill : String) (level : Int) (cands : List GrindCandidate)
    (h : skill_grind_selection_pure skill level cands ≠ "") :
    ∃ c, c ∈ cands ∧ c.code = skill_grind_selection_pure skill level cands
      ∧ c.craft_level ≤ level := by
  obtain ⟨c, hm, hc, hf⟩ := result_feasible skill level cands h
  exact ⟨c, hm, hc, hf.2.1⟩

/-- `grind_obtainable`: the selected candidate is obtainable (recipe reachable). -/
theorem grind_obtainable (skill : String) (level : Int) (cands : List GrindCandidate)
    (h : skill_grind_selection_pure skill level cands ≠ "") :
    ∃ c, c ∈ cands ∧ c.code = skill_grind_selection_pure skill level cands
      ∧ c.obtainable = true := by
  obtain ⟨c, hm, hc, hf⟩ := result_feasible skill level cands h
  exact ⟨c, hm, hc, hf.2.2.1⟩

/-- `grind_xp_positive`: the selected candidate PAYS SKILL XP. This is the role
that makes the grind terminating — the selector can never hand back a rung whose
craft sits in the server's zero-xp band, so every grind cycle moves the skill it
was invoked to raise. Before this the selector's ranking preferred whichever rung
had its materials already stockpiled, which is systematically the cheapest and
therefore greyest tier (live Robby 2026-08-05: `ash_plank` at woodcutting 15, 288
cycles, zero xp). -/
theorem grind_xp_positive (skill : String) (level : Int) (cands : List GrindCandidate)
    (h : skill_grind_selection_pure skill level cands ≠ "") :
    ∃ c, c ∈ cands ∧ c.code = skill_grind_selection_pure skill level cands
      ∧ c.xp_positive = true := by
  obtain ⟨c, hm, hc, hf⟩ := result_feasible skill level cands h
  exact ⟨c, hm, hc, hf.2.2.2⟩

/-- `step` never maps `some → none`: once the accumulator is `some`, it stays
`some` after one step. -/
theorem step_preserves_some (skill : String) (level : Int)
    (best : Option GrindCandidate) (d : GrindCandidate)
    (hb : ∃ b, best = some b) :
    ∃ b, step skill level best d = some b := by
  rcases step_cases skill level best d with hstep | ⟨hstep, _⟩
  · rw [hstep]; exact hb
  · exact ⟨d, hstep⟩

/-- A `some` accumulator is preserved across the whole fold. -/
theorem fold_preserves_some (skill : String) (level : Int) :
    ∀ (cands : List GrindCandidate) (init : Option GrindCandidate),
      (∃ b, init = some b) →
      ∃ b, List.foldl (step skill level) init cands = some b := by
  intro cands
  induction cands with
  | nil => intro init hb; simpa using hb
  | cons d rest ih =>
    intro init hb
    simp only [List.foldl_cons]
    exact ih (step skill level init d) (step_preserves_some skill level init d hb)

/-- Stepping a feasible candidate from ANY accumulator yields `some _`: if the
incoming `best` is already `some`, it is preserved; if it is `none`, then
`_beats c none = true` and the else-branch produces `some c`. -/
theorem step_feasible_some (skill : String) (level : Int)
    (best : Option GrindCandidate) (c : GrindCandidate) (hf : feasible skill level c) :
    ∃ b, step skill level best c = some b := by
  rcases step_cases skill level best c with hstep | ⟨hstep, _⟩
  · -- step returned `best`; show `best` is itself `some`
    rw [hstep]
    cases hbest : best with
    | some b => exact ⟨b, rfl⟩
    | none =>
      -- guard is false (c feasible), so step = (if _beats c none then some c else none);
      -- _beats c none = true, hence step = some c ≠ none = best, contradiction
      exfalso
      obtain ⟨hskill, hlevel, hobt, hxp⟩ := hf
      have hguard : ((!(decide (c.craft_skill = skill))) || (decide (c.craft_level > level))
          || (!c.obtainable) || (!c.xp_positive)) = false := by
        simp only [Bool.or_eq_false_iff, Bool.not_eq_eq_eq_not, Bool.not_false,
          decide_eq_true_eq, decide_eq_false_iff_not, hskill, hobt, hxp,
          and_true, true_and]
        omega
      have : step skill level none c = some c := by
        unfold step _beats
        rw [if_neg (by rw [hguard]; simp)]
        simp
      rw [hbest, this] at hstep
      exact absurd hstep (by simp)
  · exact ⟨c, hstep⟩

/-- FOLD REACHES SOME: a fold over a list that contains a feasible member, from
`none`, yields `some _`. The first feasible candidate flips `none → some`, and
`some` is preserved thereafter. -/
theorem fold_reaches_some (skill : String) (level : Int) :
    ∀ (cands : List GrindCandidate) (init : Option GrindCandidate),
      (∃ c, c ∈ cands ∧ feasible skill level c) ∨ (∃ b, init = some b) →
      ∃ b, List.foldl (step skill level) init cands = some b := by
  intro cands
  induction cands with
  | nil =>
    intro init h
    rcases h with ⟨c, hc, _⟩ | hb
    · exact absurd hc (List.not_mem_nil)
    · simpa using hb
  | cons d rest ih =>
    intro init h
    simp only [List.foldl_cons]
    rcases h with ⟨c, hc, hcf⟩ | hb
    · rcases List.mem_cons.mp hc with hcd | hcrest
      · -- the feasible member is the head: after stepping it, accumulator is `some`
        subst hcd
        exact ih (step skill level init c) (Or.inr (step_feasible_some skill level init c hcf))
      · exact ih (step skill level init d) (Or.inl ⟨c, hcrest, hcf⟩)
    · exact ih (step skill level init d)
        (Or.inr (step_preserves_some skill level init d hb))

/-- `grind_actionable` (one direction — the load-bearing one): a feasible
candidate with a non-empty code forces a non-empty result. (The selector never
returns "" while an actionable in-skill craft exists.) -/
theorem grind_actionable (skill : String) (level : Int) (cands : List GrindCandidate)
    (c : GrindCandidate) (hmem : c ∈ cands) (hf : feasible skill level c)
    (hne : ∀ d ∈ cands, d.code ≠ "") :
    skill_grind_selection_pure skill level cands ≠ "" := by
  rw [unfold_select]
  obtain ⟨b, hb⟩ := fold_reaches_some skill level cands none (Or.inl ⟨c, hmem, hf⟩)
  rw [hb]
  -- b ∈ cands (feasible-or-none init with none ⇒ membership), so b.code ≠ ""
  have hfeas := fold_some_feasible skill level cands none (by simp) b hb
  have hbmem : b ∈ cands := by
    rcases hfeas.2 with hm | hcontra
    · exact hm
    · simp at hcontra
  exact hne b hbmem

/-- `beats_prefers_higher_rate`: between two UNWANTED candidates, a strictly
higher xp-per-action rate wins — cross-multiplied, so no division and no
zero-denominator case.

THIS REPLACES `beats_prefers_cheaper_chain`, which said the strictly CHEAPER
chain always wins regardless of craft level. That was true of the ordering
until 2026-08-14 and is now false on purpose: cheapness is anti-correlated with
xp, because the cheapest in-level rung is the lowest-level one. Live Lor picked
a 13-action level-1 rung over a 59-action level-5 rung and sat at weaponcrafting
8 for 757 grind cycles. The surviving content of the old theorem is
`beats_prefers_cheaper_at_equal_level` below.

STATED FOR THE UNWANTED PAIR, deliberately. Two WANTED candidates both credit to
zero effective steps and therefore tie on rate by construction, so quantifying
this over equal-`wanted` pairs generally would be vacuously satisfied on half
its domain — the shape of hypothesis this project has shipped before while
proving nothing. -/
theorem beats_prefers_higher_rate (c b : GrindCandidate)
    (hcw : c.wanted = false) (hbw : b.wanted = false)
    (hrate : c.craft_level * b.acquire_steps > b.craft_level * c.acquire_steps) :
    _beats c (some b) = true := by
  have hne : ¬ (c.craft_level * b.acquire_steps = b.craft_level * c.acquire_steps) := by
    omega
  simp [_beats, hcw, hbw, hne, hrate]

/-- `beats_prefers_cheaper_at_equal_level`: at equal `wanted` standing and EQUAL
`craft_level`, the strictly cheaper chain still wins.

This is what survives of `beats_prefers_cheaper_chain`, and stating it
separately keeps the anti-regression guarantee that theorem was carrying:
cheapness still decides wherever it is the only thing that differs.

It holds by THREE different routes, which is why it is worth proving rather
than assuming — an unwanted pair at positive level through the rate itself
(equal levels make the rate comparison a comparison of steps), an unwanted pair
at level ZERO through the final raw-cost tie-break (both cross products collapse
to 0, so the rate ties), and a wanted pair through that same tie-break (the
credit ties their rates at zero).

WHY `0 ≤ c.craft_level` IS HERE. Without it the theorem is FALSE, and not
subtly: at `craft_level = -1` on both candidates, `acquire_steps` 1 against 2,
both unwanted, the cross products are `(-1)*2 = -2` against `(-1)*1 = -1`, so
`_beats` picks the COSTLIER rung and returns `false`. Multiplying an inequality
by a negative reverses it, and equal levels do not cancel the sign — they share
it. `craft_level` is nonnegative in the Python core (the API's craft levels start
at 1) but `Int` in the extraction, so this hypothesis excludes nothing the core
can produce; it is the same domain hypothesis `beats_prefers_wanted` below
carries, for the same reason. Non-vacuous: `craft_level 3` on both with
`acquire_steps` 7 against 11 satisfies every hypothesis. -/
theorem beats_prefers_cheaper_at_equal_level (c b : GrindCandidate)
    (hw : c.wanted = b.wanted) (hlvl : c.craft_level = b.craft_level)
    (hlvl0 : 0 ≤ c.craft_level)
    (hcost : c.acquire_steps < b.acquire_steps) :
    _beats c (some b) = true := by
  have hb0 : 0 ≤ b.craft_level := hlvl ▸ hlvl0
  cases hcw : c.wanted
  case false =>
    -- UNWANTED pair: no credit, so the rate is `level * steps` on both sides.
    simp [_beats, hcw, hw ▸ hcw, hlvl, hcost]
    by_cases heq : b.craft_level * b.acquire_steps = b.craft_level * c.acquire_steps
    · -- the rates TIE, which at equal level means the level is 0; the raw-cost
      -- tie-break decides, and it wants exactly `hcost`.
      rw [if_pos heq]; omega
    · -- the rates DIFFER, so the level is strictly positive and multiplying
      -- `hcost` through preserves its direction.
      rw [if_neg heq]
      have hne0 : b.craft_level ≠ 0 := by
        intro h; apply heq; rw [h]; simp
      have hpos : 0 < b.craft_level := by omega
      exact Int.mul_lt_mul_of_pos_left hcost hpos
  case true =>
    -- WANTED pair: both credit to zero effective steps, so both cross products
    -- are 0 and the rate cannot separate them. The raw-cost tie-break is the
    -- only thing left, which is precisely why it is not decoration.
    simp [_beats, hcw, hw ▸ hcw, hlvl, hcost]
    omega

/-- `costlier_never_beats_at_equal_level`: the converse guard — at equal `wanted`
standing and EQUAL `craft_level`, a strictly COSTLIER chain never displaces the
incumbent.

STATED BECAUSE THE ARGUMENT FOR `unwanted_not_beats_wanted` APPLIES HERE TOO. A
one-sided pin lets a clause be inverted without any theorem noticing, and after
this restatement the cost key was pinned in one direction only. There is no live
hole today — inverting the raw-cost tie-break is still caught through
`beats_prefers_cheaper_at_equal_level`'s wanted-pair and level-zero routes,
which reach that clause — but "currently caught by a neighbouring theorem's
incidental coverage" is not the same guarantee as "pinned", and it is the kind of
coverage that evaporates when the neighbour is later narrowed.

This is also what `costlier_chain_never_beats` used to say before 2026-08-14,
minus the claim it made about UNEQUAL craft levels, which the rate ordering
falsifies: a costlier chain at a higher level now wins, on purpose. Restricting
the converse to equal levels is what survives of it, exactly as
`beats_prefers_cheaper_at_equal_level` is what survives of its twin.

The `0 ≤ c.craft_level` hypothesis is load-bearing for the same reason as in
`beats_prefers_cheaper_at_equal_level`: at a negative level the
cross-multiplication reverses and the costlier rung wins. Non-vacuous: equal
level 4, `acquire_steps` 23 against 9, both unwanted. -/
theorem costlier_never_beats_at_equal_level (c b : GrindCandidate)
    (hw : c.wanted = b.wanted) (hlvl : c.craft_level = b.craft_level)
    (hlvl0 : 0 ≤ c.craft_level)
    (hcost : b.acquire_steps < c.acquire_steps) :
    _beats c (some b) = false := by
  have hb0 : 0 ≤ b.craft_level := hlvl ▸ hlvl0
  cases hcw : c.wanted
  case false =>
    simp [_beats, hcw, hw ▸ hcw, hlvl]
    by_cases heq : b.craft_level * b.acquire_steps = b.craft_level * c.acquire_steps
    · -- rates tie (level 0): the raw-cost tie-break refuses the costlier rung
      rw [if_pos heq]; omega
    · -- rates differ (level > 0): the costlier chain has the lower rate
      rw [if_neg heq]
      exact Int.mul_le_mul_of_nonneg_left (by omega) hb0
  case true =>
    simp [_beats, hcw, hw ▸ hcw, hlvl]
    omega

/-- `beats_prefers_wanted`: a WANTED candidate beats an UNWANTED incumbent.

The June 2026 guarantee — pure cheapest-chain greed had the bot craft a value-10
`apprentice_gloves` while ignoring the committed value-83 `copper_dagger`.

DERIVED, NOT ASSERTED, since 2026-08-14. `wanted` is no longer a key above the
rate; it credits `effective_steps` to zero, which zeroes the INCUMBENT's
cross-product, so the wanted candidate either wins the rate outright or ties it
at zero and wins the `wanted` tie-break underneath. Proving it is the check that
the credit and the tie-break together reproduce what the old lexicographic pivot
gave by fiat.

WHY THE TWO `0 ≤` HYPOTHESES ARE HERE, AND WHY THEY ARE NOT SLACK. The credit
zeroes the CHALLENGER's steps, so its cross product is
`c.craft_level * b.acquire_steps` while the incumbent's collapses to 0 — and a
product of two nonnegatives is what makes that "at least zero" rather than
"below zero". Let either factor go negative and the wanted rung LOSES outright,
which is the whole guarantee inverted. Both counterexamples are checked by
evaluation, not assumed:

* `c.craft_level = -1` with `b.acquire_steps = 5`: the challenger's rate is
  `-1 * 5 = -5` against the incumbent's `0`, so `_beats` returns `false` and the
  throwaway keeps the slot.
* `c.craft_level = 3` with `b.acquire_steps = -5`: the rate is `3 * -5 = -15`
  against `0`, same inversion.

Neither is reachable from the Python core — API craft levels start at 1 and an
action count cannot be negative — so the hypotheses exclude nothing real. They
are recorded here rather than only in `Formal/Contracts.lean` because this doc
comment is where a reader minded to delete a hypothesis will be standing. -/
theorem beats_prefers_wanted (c b : GrindCandidate)
    (hcw : c.wanted = true) (hbw : b.wanted = false)
    (hlvl : 0 ≤ c.craft_level) (hsteps : 0 ≤ b.acquire_steps) :
    _beats c (some b) = true := by
  -- After `simp` the goal is the disjunction the credit produces:
  -- `(c.craft_level = 0 ∨ b.acquire_steps = 0) ∨ 0 < c.craft_level * b.acquire_steps`.
  -- The two left disjuncts are the rate TIE at zero (won by the `wanted`
  -- tie-break); the right one is the outright rate win. `omega` cannot close it
  -- because the cross-product is nonlinear, so the case split is explicit.
  simp [_beats, hcw, hbw]
  by_cases h1 : c.craft_level = 0
  · exact Or.inl (Or.inl h1)
  · by_cases h2 : b.acquire_steps = 0
    · exact Or.inl (Or.inr h2)
    · exact Or.inr (Int.mul_pos (by omega) (by omega))

/-- `unwanted_not_beats_wanted`: an UNWANTED candidate NEVER displaces a wanted
incumbent — however cheap its chain or high its craft level.

THE CONVERSE GUARD, and the only Lean pin behind the `_beats invert wanted
shield` mutant. `beats_prefers_wanted` above says a keeper wins when it
challenges; this says a throwaway loses when it challenges. Both directions are
needed because they run through different clauses: the challenger's credit fires
in one and the incumbent's in the other, and a one-sided pin lets the shield
clause be inverted without any theorem noticing.

SURVIVES THE 2026-08-14 REWORK, unlike `costlier_chain_never_beats`. Under the
rate ordering the incumbent's credit zeroes `best_steps`, so the challenger's
cross product `c.craft_level * 0` is 0 while the incumbent's is
`b.craft_level * c.acquire_steps`. Either that is positive and the throwaway
loses on rate outright, or it is zero and the throwaway loses on the `wanted`
tie-break underneath.

BOTH `0 ≤` HYPOTHESES ARE LOAD-BEARING, checked by evaluation rather than
assumed. Drop `0 ≤ b.craft_level` and `b.craft_level = -2` with
`c.acquire_steps = 3` makes the incumbent's product `-6 < 0`, so the throwaway
wins. Drop `0 ≤ c.acquire_steps` and `c.acquire_steps = -3` with
`b.craft_level = 2` does the same. Both are unreachable from the Python core —
craft levels start at 1 and an action count cannot be negative — so the
hypotheses cost nothing real. Non-vacuous: an unwanted rung at level 7 / 3 steps
against a wanted incumbent at level 2 / 41 steps satisfies all four. -/
theorem unwanted_not_beats_wanted (c b : GrindCandidate)
    (hcw : c.wanted = false) (hbw : b.wanted = true)
    (hlvl : 0 ≤ b.craft_level) (hsteps : 0 ≤ c.acquire_steps) :
    _beats c (some b) = false := by
  -- `simp` reduces to: if the rates differ then the incumbent's cross product
  -- is nonnegative (so the challenger's 0 does not exceed it). The credit has
  -- already zeroed the challenger's side.
  simp [_beats, hcw, hbw]
  exact fun _ => Int.mul_nonneg hlvl hsteps

end Formal.SkillGrindSelection
