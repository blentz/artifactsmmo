# Liveness Proof Plan

**Goal:** Prove the AI makes monotonic progress toward level 50 under a faithful server model. Safety proofs (Phases 1-18) say "no bad transitions". Liveness says "good outcome eventually". Different proof shape, different machinery.

**Status:** PLANNING. No Lean work started yet.

## Claim hierarchy

Strongest to weakest. Each tier depends on lower tiers.

| Tier | Claim | Difficulty | Phase |
|------|-------|-----------|-------|
| 5 | `∀ s₀. ∃ k. (step^k s₀).level ≥ 50` — level-50 reachability from spawn | Hardest | 25 |
| 4 | `∀ s. ∃ k. (step^k s).level > s.level` — cumulative progress | Hard | 23 |
| 3 | `∀ s g. g.value(s) > 0 → ∃ plan. valid(plan, s, g)` — plan exists | Hard | 21 |
| 2 | `∀ s ∈ Reachable. ∃ g. g.value(s) > 0` — no deadlock state | Medium | 20 |
| 1 | `∀ s a. step(s, a).measure < s.measure ∨ level↑ ∨ task↑` — local progress | Tractable | 19 |
| 0 | (current safety proofs — done) | — | 1-18 |

Tier 5 = composite: needs 1-4 + game-data fixture + bounded action axioms.

## Required modeling work (none of this exists yet)

### M1: Cycle loop in Lean
Pure function `step : State → ServerResponse → State` mirroring perceive-plan-act in `src/artifactsmmo_cli/ai/cycle.py` (or wherever the loop lives — verify file path before Phase 19).

Inputs: current `State`, server's response to the previously-issued action.
Output: next `State` + next action to issue.

Decomposes as:
```
step s resp =
  let s' = perceive s resp         -- merge server response into state
  let g = arbiter.select s'         -- pick top plannable goal
  let plan = planner.search s' g    -- GOAP plan
  let a = plan.head                 -- next action
  (s', a)
```

All four sub-functions already have safety proofs. Wire them into a `step` for liveness reasoning.

### M2: Server abstraction
A typeclass `Server` with explicit axioms about server behavior. **High risk of axiom dishonesty** — each axiom must be defensible from openapi.spec.

Candidate axioms (each must survive adversarial review):
- `axiom fight_xp_positive : ∀ m, monster_level(m) ≥ level → fight(m).xp_gained > 0`
- `axiom resource_drop_eventual : ∀ r ∈ map, gather(r) finite cycles → drop received`
- `axiom cooldown_bounded : ∀ a, a.cooldown < MAX_COOLDOWN_SECONDS`
- `axiom xp_curve_finite : ∀ L, xp_to_level(L) < ∞`
- `axiom taskmaster_offers : ∀ s, accept_task(s) within K cycles → task assigned`

Each axiom = an empirical claim about the real server. Must be paired with:
- Reference to openapi.spec section that backs it.
- A replay-based conformance test in the differential harness.
- An adversarial review pass (per `feedback_proofs_tell_false_stories`).

### M3: Game-data fixture
Currently `game_data` is loaded at runtime from server. For Lean proofs, freeze a snapshot:
- Phase 24: capture `game_data` to a Lean fixture (recipes, item_stats, resource_skill, monster_level, etc.).
- Pin to a specific openapi.spec version.
- Differential: a Python test that loads live game_data and asserts it matches the fixture.
- Re-cut fixture on spec change.

Without this, Tier 5 cannot be stated concretely — "level 50 reachable" depends on what recipes/monsters/resources exist.

### M4: Ranking / measure functions
For Tier 1 (local progress) and Tier 4 (cumulative): a lexicographic measure that decreases per cycle.

Candidate measure (tuple, lex-order):
```
measure(s) = (
  XP_TO_NEXT_LEVEL(s.level) - s.xp,         -- decreases on combat
  REMAINING_TASK_CYCLES(s),                  -- decreases on task work
  PRESSURE_TO_BANK(s),                       -- decreases on deposit
  HP_DEFICIT(s),                             -- decreases on restore
)
```

Prove: `step(s, a).measure < s.measure` lex-order whenever `s.level < 50`.

Edge case: level-up resets measure[0] but increments level — handle with separate level-up case in induction.

## Mathlib decision

Current proofs: core Lean only. Axioms ⊆ `{propext, Classical.choice, Quot.sound}`.

Liveness proofs need:
- `Nat.rec` over cycles → core provides
- `Function.iterate` for `step^k` → core provides via manual recursion, Mathlib has `Function.iterate` directly
- Well-founded recursion on lex-ordered tuples → core provides via `WellFoundedRelation`
- Possible measure-decrease tactic → Mathlib has `decreasing_by` extensions

**Recommendation: stay core-only.** Quarantine all liveness modules under `Formal/Liveness/` and prove every axiom-budget regression triggers gate failure. If a specific theorem genuinely needs Mathlib, isolate it in `Formal/Liveness/Mathlib/` with explicit axiom-budget waiver.

## Phasing

### Phase 19: Tier 1 — local progress per cycle (scope: ~2 weeks of phases)
**Deliverables:**
- `Formal/Liveness/Measure.lean`: lex-tuple measure function `measure : State → ℕ⁴`.
- `Formal/Liveness/LocalProgress.lean`: theorem `step_decreases_or_levels :
    ∀ s a, valid(s, a) → measure(step(s, a)) <ₗₑₓ measure(s) ∨ levelUp(s, step(s, a))`.
- Per-action progress lemmas (FightAction, GatherAction, etc.) — each shows which measure component they decrease.
- Differential: Python loop runs 1000 cycles against a stub server, asserts measure decreases at every step (skipping no-op cooldown cycles).
- Mutations ≥3: invert measure component, drop a measure dimension, swap measure-tuple order.

**Risk:** "valid(s, a)" precondition may swallow the proof. Must specify what 'valid' means without circularity.

**Acceptance:** axiom ⊆ {propext, Classical.choice, Quot.sound}, theorem head matches commit-message claim, no false-premise hypotheses.

### Phase 20: Tier 2 — no-deadlock (every reachable state has a firing goal)
**Deliverables:**
- `Formal/Liveness/Reachable.lean`: inductive `Reachable : State → Prop` (spawn ∪ closure under step).
- Theorem `∀ s, Reachable s → ∃ g ∈ Goals, g.value(s) > 0`.
- Case-split: for each region of state space (low-HP, full-inventory, no-task, level-blocked, etc.), name the firing goal.
- Differential: Hypothesis-generated states from `Reachable` strategy, assert `max(g.value(s) for g in Goals) > 0`.

**Risk:** Reachable is co-inductive — may not enumerate cleanly. Mitigation: prove for the *closed* state space (bounded level/skill/inventory ranges), then argue every reachable state lies in it.

### Phase 21: Tier 3 — plan exists per firing goal
**Deliverables:**
- `Formal/Liveness/PlanExists.lean`: theorem `∀ s g, g.value(s) > 0 → ∃ plan, planner.search(s, g) = Some plan`.
- Per-goal-and-state-region existence proof, using the action graph.
- Differential: for each goal, Hypothesis-generated firing states, assert `planner.search(s, g) is not None`.

**Risk:** Planner is heuristic + budget-bounded. May return `None` due to budget exhaustion on valid-but-deep plans. Must distinguish "no plan exists" from "search budget exceeded". This forces a separate theorem about *the action graph itself*, not the searcher.

### Phase 22: Cycle loop in Lean (infrastructure)
**Deliverables:**
- `Formal/Liveness/Cycle.lean`: `step : State → ServerResponse → State × Action`.
- Wires existing proven primitives: ArbiterSelect, Planner, Action.apply.
- Theorem: `step` preserves all 8-field baseline (composes Phase-4 ApplyBaseline with arbiter+planner).
- Differential: Python `play.py` loop runs against stub server K cycles, asserts state evolution byte-equivalent to Lean `step^k`.

**Risk:** Real loop has perception/IO interleaved. Pure `step` must take perception as input (`ServerResponse` parameter), pushing the IO out of scope — only the pure decision/transition is in scope. State this gap honestly.

### Phase 23: Tier 4 — cumulative progress (level eventually increases)
**Deliverables:**
- `Formal/Liveness/CumulativeProgress.lean`: theorem `∀ s, s.level < 50 → ∃ k, (step^k s).level > s.level`.
- Proof: well-founded induction on measure (Tier 1) + reachable-implies-firing-goal (Tier 2) + firing-goal-implies-plan (Tier 3).
- `k` is bounded by `measure(s) * MAX_NO_OP_CYCLES`.
- Differential: Python simulator runs from arbitrary spawn-states, records cycles-to-next-level distribution.

**Risk:** Well-founded induction on a lex-tuple of large ℕs may not converge in reasonable kernel time. May need explicit bound on tuple components.

### Phase 24: Game-data fixture + openapi conformance harness
**Deliverables:**
- `formal/Formal/Liveness/GameDataFixture.lean`: hard-coded snapshot of recipes, monster_level, resource_skill, item_stats (only the fields the proofs touch).
- `formal/diff/test_game_data_fixture_diff.py`: loads live game_data, asserts fields match fixture; flags spec drift.
- `formal/diff/snapshot_game_data.py`: re-cut fixture on spec change (tool, not run in CI).
- Document the openapi.spec version pinned to.

**Risk:** Fixture size may exceed Lean kernel reasonable limits. Mitigation: include only the subset needed for Tier 5 reasoning; reject "kitchen-sink" approach.

### Phase 25: Tier 5 — level-50 reachability (capstone)
**Deliverables:**
- `Formal/Liveness/LevelFiftyReachable.lean`: theorem `∀ s₀ ∈ SpawnStates, ∃ k, (step^k s₀).level ≥ 50` under the GameDataFixture.
- Proof: iterate Tier 4 forty-nine times (level 1 → 50) with explicit k-bound per level.
- Bound: `K_total = Σ_{L=1}^{50} measure_max(L) · MAX_NO_OP`.
- Differential: end-to-end simulator runs N starts, asserts every one reaches level 50 within K_total cycles against stub server.

**Risk:** Stub server must faithfully implement the Server axioms (M2). Differential catches gross axiom dishonesty.

## What this plan does NOT prove

State up front, do not let scope creep claim them later:
- **Network / concurrency**: server temporal axioms abstract away race conditions, real cooldowns vs wall-clock drift, transient API errors. Liveness here means "deterministic progress against a faithful sequential server abstraction", not "robust against arbitrary network failure".
- **Probabilistic drops**: server axioms encode "eventually drops within K cycles", not the actual probability distribution. Real RNG is out of scope.
- **Multi-player contention**: assumed solo. Other players consuming resource nodes / killing monster spawns is unmodeled.
- **TUI / CLI / persistence**: proofs cover the deterministic decision core only.
- **API conformance is asserted via the fixture diff test, not proven** — the fixture is a snapshot, not a formal mapping from openapi.spec to game_data parser code.

## Honesty gates (mandatory, per `feedback_proofs_tell_false_stories`)

Each phase's commit message MUST disclose:
- Any false-premise hypotheses in the proofs (none allowed; if used, theorem retracted).
- Any axiom added beyond `{propext, Classical.choice, Quot.sound}` (each requires user approval + openapi-backed justification).
- Any "header-only" theorem where the proof is trivial but the production function is non-trivial.
- Any state-space region the proof excludes (must name the excluded region; can't hide behind "assume reasonable input").

Adversarial review per phase: dispatch a reviewer subagent to look for theater patterns. If the headline theorem can be made true by choosing a vacuous premise, FAIL.

## Order-of-attack rationale

Tier 1 (Phase 19) first because:
- Smallest scope; tractable in 1-2 phases.
- Catches measure-function design problems early (cheap to revise before Tiers 4-5 depend on it).
- Produces immediate value (proves the AI doesn't *regress*, which is itself meaningful).

Phase 22 (cycle loop) is infrastructure for Tiers 4-5; deferred until after Tiers 1-3 to avoid building it before knowing the exact shape needed.

Phase 24 (game-data fixture) deferred until Phase 25 needs it — fixture is the costliest piece (kernel elaboration risk) and only Tier 5 strictly requires it.

## Decisions (user-approved 2026-05-30)

1. **Mathlib: APPROVED.** Take dependency. Quarantine to `Formal/Liveness/`; existing safety modules stay core-only (preserve their axiom-clean status). Gate `check_axioms.sh` splits: safety modules ⊆ `{propext, Classical.choice, Quot.sound}`; liveness modules allowed Mathlib's standard axiom set, disclosed per-theorem in commit messages.
2. **Server axiom approval: per-axiom user signoff** with openapi.spec section citation. Each new axiom in `Formal/Liveness/Server.lean` gets a docstring header `-- AXIOM-ID: SRV-NNN | spec: <section> | approved: <date>`. No silent additions.
3. **Stub server location: `formal/sim/`.** Isolated from `tests/`. Python `FakeServer` implements the Server axioms; differential conformance tests live in `formal/diff/`.
4. **Game-data fixture: pinned;** refresh on user request only. Spec version recorded in `formal/Formal/Liveness/GameDataFixture.lean` docstring.

## Done-state

Phase 25 commits a theorem of the form:
```lean
theorem ai_reaches_level_fifty :
    ∀ s₀ ∈ SpawnStates,
      ∃ k ≤ K_LEVEL_50_BOUND,
        (Nat.iterate (step server) k s₀).level ≥ 50
```
…with axioms ⊆ `{propext, Classical.choice, Quot.sound, server_axioms}`, where `server_axioms` is an explicit, openapi-backed, user-approved list and every axiom has a passing replay-based conformance test.

If we ship this, we will have proven what the meta-goal stated: **"given the openapi.spec and our project design specs as inputs, we have built an AI bot capable of interfacing with the APIs in provably valid ways for all possible encounterable scenarios"** — to the precise extent that the server-axiom set is honest.

## Phasing status

| Phase | Scope | Status | Commit |
| --- | --- | --- | --- |
| 19a | Infrastructure: Mathlib pin, `Formal/Liveness/` namespace, split axiom gate | DONE | f6edd18 |
| 19b | `Measure.lean` (5-tuple) + Fight progress lemma + LIV-001 axiom | DONE | f9a91d1 |
| 19c | Gather/Deposit/Rest lemmas + headline + measure expanded to 6-tuple | DONE | 4f04fe9 |
| 19d | FakeServer + 1000-cycle differential + LIV-001 replay + 4 mutations | DONE | 77c8748 |
| 20-retracted | Phase 20a (abea964) + Phase 20b (aacbc6d) RETRACTED 2026-05-31. Coarse 8-region `FiringGoal` aggregated production's 17-means ladder; `goalValueOf` was constant-per-constructor; drop/reorder mutations survived because the model wasn't a structural mirror. User-approved Option C: restart Tier 2 at production granularity. Reverts: 6a01... + 3529945. | RETRACTED | — |
| 20-redesign | Tier 2 v2 (production-granularity from day 1) | TODO | — |
| 20a-v2 | `Formal/Liveness/MeansKind.lean`: enum mirroring production GUARD_ORDER+COLLECT_REWARD_ORDER+step+DISCRETIONARY_ORDER (17 constructors); `productionLadder : State → Option MeansKind` mirroring `_fires` predicates from `tiers/guards.py` + `tiers/means.py`. | TODO | — |
| 20b-v2 | Per-MeansKind firing lemma: each constructor of `MeansKind` has a State predicate (the production `_fires` mirror) such that when true, the production goal's value > 0 (cite Phase-18 GoalSystem.lean). | TODO | — |
| 20c-v2 | Headline: `∀ s, productionLadder s ≠ none` (no-deadlock at production granularity). Proven by case-split on State; falls through to DISCRETIONARY tier (PursueTask/AcceptTask cover task axis with `taskValid`). | TODO | — |
| 20d-v2 | Python mirror `formal/sim/production_ladder.py` calling real `select_pure` against real candidate list; differential equivalence Hypothesis test. | TODO | — |
| 20e-v2 | Mutations targeting GUARD_ORDER / COLLECT_REWARD_ORDER / DISCRETIONARY_ORDER tuple reorderings + per-`_fires` predicate flips. Drop/reorder mutations now killable because the Lean model is a structural mirror. | TODO | — |
| 21  | Tier 3 — plan exists per firing goal | TODO | — |
| 22  | Cycle loop in Lean | TODO | — |
| 23  | Tier 4 — cumulative progress | TODO | — |
| 24  | Game-data fixture + openapi conformance harness | TODO | — |
| 25  | Tier 5 — level-50 reachability (capstone) | TODO | — |

Phase 19a notes: Mathlib pinned to **v4.30.0** (matching `formal/lean-toolchain`'s Lean 4.30.0). At this pin the foundational Mathlib axiom set coincides with the safety set `{propext, Classical.choice, Quot.sound}`, so the liveness allow-list does not need to grow beyond the kernel three. The split gate (`check_axioms_safety.sh` + `check_axioms_liveness.sh`) and the cross-namespace leak check are wired into `gate.sh` via the existing `check_axioms.sh` entry point.
