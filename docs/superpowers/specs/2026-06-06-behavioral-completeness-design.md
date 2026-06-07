# Design: Behavioral Completeness + Proven Core (Bug-Free AI Program)

Date: 2026-06-06
Status: Approved (brainstorming) — pending Phase 0–1 implementation plan
Scope of THIS spec: the program **framework** + **Phase 0–1** (build the audit
matrix, the content-tier generator, the concept↔proof traceability index, and
complete the audit → ranked gap backlog). Each gap-closure (Phase 2…N) is a
separate spec spawned from the backlog.

## Goal

Drive the ArtifactsMMO AI player to **behavioral completeness with a proven
core**: every game concept has a deliberate, documented strategic policy (act /
exploit / ignore-with-reason) — no concept silently unhandled — AND the decision
logic for each is proven correct in Lean 4 over all inputs. "Bug-free" =
(no unconsidered behavior) ∧ (no unproven decision).

This is a multi-session *program*, not a single feature. This spec establishes
the framework and the foundational audit that drives all subsequent work.

## Success criterion

A concept row is "done" when:
1. its **policy** is non-empty and justified (act/exploit/ignore-with-reason), and
2. its **proof-coverage** satisfies the four property classes *where meaningful*
   (see below), traceable to named Lean theorems.

The program is "complete" when every concept row is done.

## The four proof property classes (the "proven core" contract)

For each strategic behavior, prove in Lean (kernel-checked, axiom-clean) the
classes that apply:

- **Dominance & monotonicity** — the ranking never places a strictly-dominated
  option above the option that dominates it; value is monotone in the inputs that
  should raise it (more progress toward a goal never lowers its rank; lower cost
  never lowers it). Catches ranking inversions — the bug class that stalled the
  live bot (a depth-gated gear step with no fallback losing to doomed goals).
- **Totality & no-deadlock** — every reachable state maps to a defined, non-empty
  policy; the behavior is never the sole option yet unfireable. Extends
  `NoActionDeadlock` / liveness.
- **Safety invariants** — the behavior never violates a hard constraint
  (keep-set / task-materials, recycle-protect, inventory cap, gold floor,
  winnability gate, …). One invariant theorem per constraint, across all
  behaviors.
- **Reachability / progress** — from any state the behavior advances (or at least
  never blocks) the next content-unlock tier. Extends `LevelFiftyReachable` /
  liveness-chain.

"Optimal play" is explicitly NOT a proof target (not well-defined/decidable). The
proofs guarantee structural soundness, not optimality.

## Sourcing (3 cross-referenced authorities)

Every strategic claim in the matrix cites its source — no uncited assertions.

1. **Concept inventory + content-tiers** ← the openapi spec
   (`openapi.json`: paths = `accounts, achievements, badges, characters, effects,
   events, grandexchange, items, leaderboard, maps, monsters, npcs, resources,
   simulation, tasks`) + live encyclopedia API data (items / monsters / resources
   / effects / achievements / events). The **content-tier table is GENERATED**
   from level-requirement data, not hand-written, so it stays accurate.
2. **Mechanics / semantics** ← artifactsmmo.com docs, fetched per concept for what
   the API returns as data but does not *explain* (GE fee/escrow rules, effect
   stacking, achievement reward semantics, event spawn cadence). Captured as cited
   notes per row.
3. **Current coverage** ← the code (`src/.../ai/goals/`, `src/.../ai/tiers/`) and
   the proofs (`formal/`).

## Artifact 1 — `docs/behavioral_completeness/MATRIX.md`

One row per game concept. Columns:

| Column | Captures | Source |
|---|---|---|
| Player → concept | actions the player takes on it | openapi paths |
| Concept → player | effects it has on the player (drops, gold, buffs, gates, rewards) | game data + docs |
| Strategic uses | why/when to engage it | docs + reasoning |
| Opportunity cost × tier | per content-tier: cost of engaging vs what it enables/forecloses | tier table + docs |
| Behavior coverage | current goal/means/guard handling (or "none") | `goals/`, `tiers/` |
| Proof coverage | named theorems backing it, tagged by property class | `formal/` |
| Gap + policy | classified gap (MISSING/THIN/UNPROVEN/WRONG-POLICY/IGNORE) + the deliberate policy | synthesis |

Concept rows (initial): characters, maps, monsters, resources, items/crafting,
tasks, bank, npcs, events, effects/consumables, grandexchange, achievements,
badges, leaderboard, simulation. (Refined during the audit; combat is part of
monsters/simulation.)

## Artifact 2 — content-tier table (generated)

`docs/behavioral_completeness/content_tiers.md` (+ the generator script). The
**journey axis**: capability-unlock tiers derived by clustering item / monster /
resource / task **level-requirement** data into bands defined by what each band
unlocks (e.g. copper→iron→steel gear/tools, bank unlock, new map regions, monster
tiers, task tiers). Opportunity cost is always evaluated against *this* axis:
"what does reaching the next unlock cost vs. what it enables." Generated from live
game data so it can't drift from the real game.

## Artifact 3 — concept↔proof traceability

Bidirectional, **mechanically checked**:

- **Per-concept (forward):** the MATRIX "Proof coverage" cell names the theorems
  and the property class(es) each discharges. Empty cells = visible proof gaps.
- **Per-proof (inverse):** `docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md`,
  one row per `formal/` module → concept(s) modeled + property class(es)
  discharged. Surfaces (a) concepts with zero proofs and (b) proofs tied to no
  concept (abstract/orphan theorems that look rigorous but back nothing real).
- **Mechanism:** each `formal/Formal/<Module>.lean` gets a one-line header tag,
  e.g. `-- @concept: combat, monsters @property: safety, dominance`. A script
  (`formal/gate/check_proof_concept_index.sh`) greps these tags, regenerates the
  index, and cross-checks against `Manifest.lean` so the index cannot silently
  drift. Modules with no tag (or tags naming no real concept) fail the check.

## Gap taxonomy + prioritization

Each row's gap is classified:

| Kind | Meaning | Work |
|---|---|---|
| MISSING | no policy at all | full brainstorm→prove→build |
| THIN | behavior exists but naive/incomplete | extend + prove |
| UNPROVEN | behavior + tests exist, missing ≥1 proof class | prove only |
| WRONG-POLICY | behavior exists but strategically incorrect | redesign + prove |
| IGNORE | deliberately not actioned | record justification, done |

**Prioritization = leverage score** per gap:
`journey-impact × live-bottleneck × stall-risk`, where
- journey-impact = how much it unblocks content-tier progression (tier table),
- live-bottleneck = is this the current binding constraint (read from traces /
  play data),
- stall-risk = does the gap cause stuck/incoherent behavior.

Highest score first. The audit outputs a **ranked gap backlog**.

## Per-gap delivery loop (Phase 2…N, one concept-behavior at a time)

1. **Brainstorm** the policy: act/exploit/ignore at each content-tier + the
   opportunity-cost rationale.
2. **Spec** the decision function + plug-point (guard / means / objective-root) +
   the applicable proof obligations.
3. **formal-development**: prove the decision core in Lean FIRST (the 4 classes
   where meaningful), then implement to mirror, guarded by differential + mutation
   + ≥90% (repo: 100%) coverage.
4. **Live-validate**: run the bot; confirm via trace / py-spy the behavior fires
   at the right tier and advances the journey.
5. **Close the row**: update MATRIX + PROOF_CONCEPT_INDEX (tags + checked index),
   commit.

## Program decomposition

- **Phase 0 — Foundation (this spec):** build `MATRIX.md` skeleton, the
  content-tier generator + `content_tiers.md`, `PROOF_CONCEPT_INDEX.md` + the
  tag-grep checker wired into the gate, and back-tag the existing 116 formal
  modules with `@concept`/`@property` headers.
- **Phase 1 — Audit (this spec):** fill every MATRIX row across all 3 sources →
  produce the ranked gap backlog. Deliverable = the completed map.
- **Phase 2…N — Close gaps (separate specs):** each backlog item runs the delivery
  loop, highest-leverage first.
- **Continuous:** live play data re-scores priorities and surfaces new
  WRONG-POLICY gaps.

## Out of scope (YAGNI)

- Closing any specific gap (those are Phase 2…N specs).
- Proving "optimal play."
- Multi-character / account-level strategy (single-character leveling journey
  first).
- A UI for the matrix (it's a markdown + checked index).

## Risks / open items

- **Tier generation fidelity:** clustering level-requirement data into tiers is a
  heuristic; validate the generated tiers against the game docs and live play, and
  allow a small curated override file with justification.
- **Docs fetch volume:** per-concept artifactsmmo.com fetches are token-heavy; do
  them lazily per concept during the audit, cache the cited notes in the row.
- **Tag drift on 116 modules:** back-tagging is bulk work; the checker makes drift
  a hard failure, but the initial tagging needs a careful pass (some modules are
  abstract/structural and map to a "core/infra" pseudo-concept, not a game
  concept — that is an allowed tag, recorded explicitly).
- **Index honesty:** a module tagged with a concept it doesn't actually model is
  the inverse of the orphan problem; the audit's Phase-4-style adversarial review
  must spot-check that tags are truthful, not just present.
