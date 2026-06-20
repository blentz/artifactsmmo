import Mathlib.Tactic

/-! # StickySelect — Tier-2 root sticky selection + progress-gated release

Models the Tier-2 sticky-commitment step of `StrategyEngine.decide`
(`src/artifactsmmo_cli/ai/tiers/strategy.py:582-595`) — the logic that, AFTER the
`decide_key` sort produces the ranked candidate list, may override the top-scored
root with the previous cycle's `chosen_root` ("sticky") when the top does not
*dominate* it by `STICKY_DOMINANCE_RATIO`.

This module also models the **progress-gated release** (the fix, 2026-06-20): the
feedback of `last_chosen_root` into the next cycle is gated on whether the
committed root actually made measure progress this cycle, REPLACING the broken
`chosen_step_alive` gate (`player.py:340`) that merely checked whether a goal
*object* was produced — a check a never-executing zombie grind passes forever.

## The zombie livelock (trace play-trace-Robby.jsonl, 1028-cycle hold)

`chosen_root = ReachSkillLevel(weaponcrafting,5)` held for 1028 consecutive cycles
while weaponcrafting xp stayed frozen at 75: the committed grind goal
(`GatherMaterials(copper_dagger)`) produced a non-None goal object every cycle
(so `chosen_step_alive = true`) but won arbitration in 0 of them, so the skill
never leveled and the sticky anchor re-committed forever.

## What is proved here (the no-zombie core)

* `sticky_requires_progress` — the ONLY way the sticky override keeps a non-top
  root `c` is if `c` was the previous `chosen_root` AND it progressed last cycle.
  Contrapositive: **a non-progressing root is never sustained by the sticky
  override** — next cycle it loses to the (legitimately) top-scored root. This is
  the no-zombie guarantee.
* `sticky_progress_safe` — the same fact holds for ANY `ratio` (the dominance
  ratio is NOT the liveness lever; `STICKY_DOMINANCE_RATIO = 3/2` is provably
  liveness-safe). Re-derives the "correct weight": ratio ≥ 1 keeps anti-flap
  stickiness while the progress-gate prevents zombies, for every ratio.
* `released_picks_top` — once released (`lastChosen = none`), the chosen root is
  the top-scored (max) candidate. So after a zombie releases, the highest-value
  *plannable* root wins — gear-first bootstrap ordering is preserved by the
  category scores, not by the sticky.
* Non-vacuity witnesses (`kept_when_progressing`, `dropped_when_frozen`) — a
  concrete progressing run KEEPS its root; a concrete frozen run DROPS it. Rules
  out a vacuous `False → P` reading.

Faithfulness note: `Cand` carries only `repr` and `score` — the two fields the
sticky math at strategy.py:586-595 reads. The candidates are taken ALREADY SORTED
(the `decide_key` sort is proved separately in `Formal/DecideKey.lean`); this
module models the post-sort sticky override exactly. `progressed : Bool` is the
sub-measure-descent signal the impure layer computes; a differential harness binds
it to production (see `docs/PLAN_zombie_progress_gate.md`).

Liveness namespace — Mathlib permitted (uses `Rat` ordering for the `Fraction`
dominance comparison).
-/

namespace Formal.Liveness.StickySelect

/-- A ranked objective-root candidate, reduced to the two fields the Tier-2 sticky
    override reads: its `repr` (identity key, matched against `last_chosen_root`)
    and its blended `score` (the Python `final : Fraction`). -/
structure Cand where
  repr  : String
  score : Rat
deriving DecidableEq, Repr

/-- The Tier-2 sticky override, mirroring `strategy.py:582-595` AFTER the
    `decide_key` sort. `cands` is the ranked list (head = top-scored). `lastChosen`
    is the previous cycle's `chosen_root` repr (`None` ⇒ no sticky, e.g. first
    cycle or just-released). `ratio` is `STICKY_DOMINANCE_RATIO`.

    Faithful transcription:
    * empty list ⇒ no choice;
    * `last_chosen_root is None` ⇒ keep top;
    * `last_chosen_root == repr(top_root)` ⇒ keep top (no override);
    * else find the sticky candidate; if absent (satisfied/unreachable this cycle)
      ⇒ keep top; if present and `top_final ≤ ratio · sticky_final` ⇒ KEEP sticky;
      otherwise top dominates ⇒ keep top. -/
def stickyChoose (cands : List Cand) (lastChosen : Option String) (ratio : Rat) :
    Option Cand :=
  match cands with
  | []        => none
  | top :: _  =>
    match lastChosen with
    | none    => some top
    | some lc =>
      if lc = top.repr then some top
      else match cands.find? (fun c => c.repr = lc) with
        | none        => some top
        | some sticky => if top.score ≤ ratio * sticky.score then some sticky else some top

/-- The progress-gated feedback (the fix). The chosen root's repr is fed back as
    next cycle's `lastChosen` ONLY when it progressed; otherwise the anchor is
    released (`none`). Replaces the `chosen_step_alive` gate at `player.py:340`. -/
def nextLast (chosen : Option Cand) (progressed : Bool) : Option String :=
  match chosen with
  | some c => if progressed then some c.repr else none
  | none   => none

/-- `stickyChoose` always returns a member of `cands` (or `none` when empty). -/
theorem stickyChoose_mem {cands : List Cand} {lc : Option String} {ratio : Rat}
    {c : Cand} (h : stickyChoose cands lc ratio = some c) : c ∈ cands := by
  unfold stickyChoose at h
  cases cands with
  | nil => simp at h
  | cons top rest =>
    cases lc with
    | none => simp at h; subst h; exact List.mem_cons_self
    | some lc =>
      simp only at h
      by_cases hlc : lc = top.repr
      · simp [hlc] at h; subst h; exact List.mem_cons_self
      · simp only [hlc, if_false] at h
        cases hfind : (top :: rest).find? (fun c => c.repr = lc) with
        | none => simp [hfind] at h; subst h; exact List.mem_cons_self
        | some sticky =>
          simp only [hfind] at h
          by_cases hdom : top.score ≤ ratio * sticky.score
          · simp [hdom] at h; subst h; exact List.mem_of_find?_eq_some hfind
          · simp [hdom] at h; subst h; exact List.mem_cons_self

/-- When `lastChosen = none` (released, or first cycle), the chosen root is exactly
    the top-scored candidate. So after a zombie RELEASES, the highest-value
    candidate wins the next cycle — the gear-first bootstrap ordering is carried by
    the category scores, never by a stale sticky anchor. -/
theorem released_picks_top {cands : List Cand} {ratio : Rat} {top : Cand}
    (hhead : cands.head? = some top) :
    stickyChoose cands none ratio = some top := by
  unfold stickyChoose
  cases cands with
  | nil => simp at hhead
  | cons hd tl => simp only [List.head?_cons, Option.some.injEq] at hhead; simp [hhead]

/-- **No-zombie core.** If a root `c` is the chosen root two cycles running, and on
    the second cycle it is NOT the top-scored candidate (so it was kept purely by
    the sticky override), then it MUST have progressed on the first cycle.

    Contrapositive (the livelock killer): a non-progressing committed root
    (`prog₀ = false`) is released — at the next cycle it can only remain chosen by
    legitimately becoming the top-scored candidate, never as a frozen sticky
    anchor. The 1028-cycle weaponcrafting hold (frozen skill xp ⇒ `prog₀ = false`,
    yet not top-scored — gear out-scored it 2.5 > 2.04) is therefore impossible. -/
theorem sticky_requires_progress
    {cands₁ : List Cand} {ratio : Rat} {c : Cand} {prog₀ : Bool}
    (hchoose : stickyChoose cands₁ (nextLast (some c) prog₀) ratio = some c)
    (hnottop : cands₁.head? ≠ some c) :
    prog₀ = true := by
  by_contra hp
  simp only [Bool.not_eq_true] at hp
  -- prog₀ = false ⇒ nextLast (some c) false = none ⇒ chosen = top, contradicting hnottop
  have hnl : nextLast (some c) prog₀ = none := by simp [nextLast, hp]
  rw [hnl] at hchoose
  cases cands₁ with
  | nil => simp [stickyChoose] at hchoose
  | cons top rest =>
    have htop : stickyChoose (top :: rest) none ratio = some top :=
      released_picks_top (by simp)
    rw [htop] at hchoose
    exact hnottop (by rw [List.head?_cons]; exact hchoose)

/-- **The dominance ratio is not the liveness lever.** `sticky_requires_progress`
    holds for EVERY `ratio : Rat` — the progress-gate, not the magnitude of
    `STICKY_DOMINANCE_RATIO`, is what prevents zombies. Hence `ratio = 3/2`
    (production) is liveness-safe, and so is any ratio: the "correct weight" for the
    dominance ratio is "anything ≥ 1 for anti-flap; liveness holds regardless." -/
theorem sticky_progress_safe (ratio : Rat)
    {cands₁ : List Cand} {c : Cand} {prog₀ : Bool}
    (hchoose : stickyChoose cands₁ (nextLast (some c) prog₀) ratio = some c)
    (hnottop : cands₁.head? ≠ some c) :
    prog₀ = true :=
  sticky_requires_progress hchoose hnottop

/-- **Non-vacuity (kept).** A concrete progressing run: a root that scores below the
    top (skill 2.04 < gear 2.5) but is the previous choice and PROGRESSED is KEPT by
    the sticky override under `ratio = 3/2` (since 2.5 ≤ 3/2 · 2.04 = 3.06). Shows
    the sticky mechanism still works for legitimately-progressing commitments. -/
theorem kept_when_progressing :
    stickyChoose [⟨"gear", 5/2⟩, ⟨"skill", 51/25⟩] (nextLast (some ⟨"skill", 51/25⟩) true) (3/2)
      = some ⟨"skill", 51/25⟩ := by
  have hineq : (5/2 : Rat) ≤ (3/2) * (51/25) := by norm_num
  show stickyChoose [⟨"gear", 5/2⟩, ⟨"skill", 51/25⟩] (some "skill") (3/2) = _
  simp only [stickyChoose, List.find?_cons, String.reduceEq, reduceIte, decide_true,
    decide_false]
  rw [if_pos hineq]

/-- **Non-vacuity (dropped).** The SAME configuration, but the sticky root did NOT
    progress (`progressed = false`): it is RELEASED and the top-scored `gear` wins.
    This is exactly the weaponcrafting zombie's correct resolution. -/
theorem dropped_when_frozen :
    stickyChoose [⟨"gear", 5/2⟩, ⟨"skill", 51/25⟩] (nextLast (some ⟨"skill", 51/25⟩) false) (3/2)
      = some ⟨"gear", 5/2⟩ := by
  show stickyChoose [⟨"gear", 5/2⟩, ⟨"skill", 51/25⟩] none (3/2) = _
  exact released_picks_top rfl

/-! ## No infinite zombie hold — the liveness payoff (Phase 1b)

The 1028-cycle weaponcrafting hold is the failure mode this whole module exists to
rule out. `sticky_requires_progress` forbids a *single* unproductive sticky re-hold;
composed with well-foundedness of the reach-50 measure it forbids an *infinite* one.
-/

/-- **No infinite zombie hold.** For ANY well-founded relation `r` (the strict
    measure-descent order) and measure `μ : σ → β` over the per-cycle state, if a
    root `c` is the sticky-held (NON-top) choice at every cycle, then a contradiction
    follows — such an infinite hold is impossible.

    Proof: `sticky_requires_progress` forces the progress signal `prog k = true` on
    every sustained-hold step; `hprogFaithful` then yields a strictly `r`-descending
    sequence `μ (st 0) ⊐ μ (st 1) ⊐ …`, which a well-founded `r` forbids (no infinite
    descending chain). This is the formal "the zombie cannot occur once the sticky
    feedback is progress-gated."

    Instantiation: take `r := Measure.measureLt` (well-founded via
    `Measure.measureLt_wellFounded`) and `μ := Measure.measure ∘ projection`. The one
    remaining obligation is `hprogFaithful` — that production's `progressed` Bool
    really does witness a strict measure descent. That is the model↔code trust
    boundary, discharged by the differential harness (Phase 3,
    `test_sticky_select_diff.py`), NOT assumed gratis here — mirroring the existing
    `objectiveStepIsFight` arming-differential pattern (PerceptionRefresh.lean). -/
theorem no_infinite_sticky_hold
    {σ β : Type} (r : β → β → Prop) (wf : WellFounded r) (μ : σ → β)
    (st : Nat → σ) (cands : Nat → List Cand) (ratio : Rat) (c : Cand) (prog : Nat → Bool)
    (hprogFaithful : ∀ k, prog k = true → r (μ (st (k + 1))) (μ (st k)))
    (hchosen : ∀ k, stickyChoose (cands (k + 1)) (nextLast (some c) (prog k)) ratio = some c)
    (hnottop : ∀ k, (cands (k + 1)).head? ≠ some c) :
    False := by
  -- Every sustained-hold step must have progressed (the no-zombie core).
  have hprog : ∀ k, prog k = true := fun k =>
    sticky_requires_progress (hchosen k) (hnottop k)
  -- Hence the measure strictly descends on every cycle.
  have hdesc : ∀ k, r (μ (st (k + 1))) (μ (st k)) := fun k => hprogFaithful k (hprog k)
  -- A well-founded relation has no infinite descending chain: the range of `μ ∘ st`
  -- has an `r`-minimal element, but its successor sits strictly below it.
  obtain ⟨_, ⟨n, rfl⟩, hmin⟩ :=
    wf.has_min (Set.range (fun k => μ (st k))) ⟨_, ⟨0, rfl⟩⟩
  exact hmin _ ⟨n + 1, rfl⟩ (hdesc n)

end Formal.Liveness.StickySelect
